# 05 — Miscellaneous correctness + perf cleanups

Three small fixes that don't justify their own sub-plan but are
worth landing together. Each is independent; pick whichever order
suits review.

## A — `force_update_all_failed_imports` queue spam

`failed_imports.py:13-20`:

```python
def _force_update_failed_imports(self, library_id) -> None:
    failed_import_paths = FailedImport.objects.filter(
        library=library_id
    ).values_list("path", flat=True)
    for path in failed_import_paths:
        event = FSEvent(src_path=path, change=FSChange.modified)
        task = FSEventTask(library_id, event)
        self.librarian_queue.put(task)
```

For a library with thousands of failed imports (typical: corrupt
CBRs that the user wants to retry after a comicbox upgrade), this
puts thousands of `FSEventTask` items on the librarian queue. The
librarian processes them serially — each fires its own debounce,
its own filesystem stat, its own database lookup. Per-path
overhead dominates.

### Fix

`FSEventTask` already exists for single events; adding a
multi-event variant is one option but the simpler win is to
short-circuit the per-event handling:

```python
def _force_update_failed_imports(self, library_id) -> None:
    failed_import_paths = tuple(
        FailedImport.objects.filter(library=library_id).values_list(
            "path", flat=True
        )
    )
    if not failed_import_paths:
        return
    # One ImportTask covering all paths instead of N FSEventTasks
    # routed individually through the watcher debounce.
    task = ImportTask(
        library_id=library_id,
        files_modified=frozenset(failed_import_paths),
    )
    self.librarian_queue.put(task)
```

This dispatches the importer once with all paths, exactly the
shape the importer expects. The per-task overhead drops from
O(N paths) to O(1).

**Caveat**: `ImportTask` skips the FS-event debounce that
`FSEventTask` flows through. For a "force" operation that's the
correct behavior — the user explicitly requested re-import.

### Risk

If the watcher's debounce was de-duplicating identical
re-events, that's lost. In practice the FailedImport table only
contains one row per path, so the debounce wasn't doing
de-duplication work — it was just adding overhead.

## B — `adopt_orphan_folders` iteration cap

`adopt_folders.py:48-76`:

```python
def adopt_orphan_folders(self) -> None:
    self.abort_event.clear()
    ...
    for library in libraries.iterator():
        folders_left = True
        while folders_left:
            if self.abort_event.is_set():
                return
            folders_left, count = self._adopt_orphan_folders_for_library(library)
            total_count += count
```

`while folders_left:` continues as long as
`_adopt_orphan_folders_for_library` keeps reporting orphans. If
the importer fails to actually move them (permission errors, FS
race), this can loop indefinitely.

### Fix

Add an iteration cap. Same shape as sub-plan 02:

```python
_ADOPT_FOLDERS_MAX_PASSES = 10

for library in libraries.iterator():
    for pass_num in range(_ADOPT_FOLDERS_MAX_PASSES):
        if self.abort_event.is_set():
            return
        folders_left, count = self._adopt_orphan_folders_for_library(library)
        total_count += count
        if not folders_left:
            break
    else:
        self.log.warning(
            f"Adopt orphan folders for {library.path} hit "
            f"{_ADOPT_FOLDERS_MAX_PASSES}-pass cap without "
            "converging — folders may be unreachable or unwriteable."
        )
```

10 passes is generous; legitimate orphan-folder graphs converge
in 1-2 passes (each pass moves orphans to their correct parent
position; second pass catches the rare case where moving an
orphan reveals more orphans).

### Risk

Cap firing on a real-world case is unlikely but possible (e.g.,
a library with thousands of orphan folders all sharing a missing
parent). The warn-and-continue path lets the next nightly retry;
no data loss.

## C — `cleanup_sessions` chunked validation

`cleanup.py:175-208`:

```python
for encoded_session in Session.objects.all():
    try:
        signing.loads(...)
    except Exception:
        bad_session_keys.add(encoded_session.session_key)
```

`Session.objects.all()` materializes all sessions. For a long-
running install with years of accumulated anonymous sessions
(opens before login, etc.), this can be tens of thousands of
rows pulled into RAM at once.

### Fix

Use `.iterator()` to stream + validate:

```python
bad_session_keys = []
for encoded_session in Session.objects.only("session_key", "session_data").iterator(chunk_size=1000):
    try:
        signing.loads(
            encoded_session.session_data,
            salt=salt,
            serializer=serializer,
        )
    except Exception:
        bad_session_keys.append(encoded_session.session_key)

if bad_session_keys:
    # Batch the delete to stay under SQLite's variable cap.
    for start in range(0, len(bad_session_keys), 30000):
        batch = bad_session_keys[start : start + 30000]
        Session.objects.filter(session_key__in=batch).delete()
```

`iterator(chunk_size=1000)` keeps memory bounded. The
`.only("session_key", "session_data")` skips loading
`expire_date` (already filtered separately).

### Risk

`iterator()` doesn't play with prefetch_related (none used
here, ✓). On SQLite specifically, iterator with chunk_size still
works correctly per Django docs.

## Suggested commit shape

Three commits in one PR (each independently revertable):

1. **`failed_imports: dispatch single ImportTask instead of N FSEventTasks`** — A. ~10 LOC change to `failed_imports.py`.
2. **`adopt_folders: iteration cap with warning`** — B. ~15 LOC change to `adopt_folders.py`.
3. **`cleanup_sessions: stream + chunk session validation`** — C. ~20 LOC change to `cleanup.py`.

Total ~45-60 LOC across three files. No correctness regression
in any of them.

## Correctness invariants

- **A — Same paths re-imported**: The ImportTask(files_modified)
  flow is the established shape for "re-import these specific
  paths" used by the importer. Honors all the importer's existing
  per-path handling (mtime check, comicbox extraction, etc.).
- **B — Cap warning fires loud**: log level `warning`, message
  references the specific library so the user can investigate.
  Same level the FK cleanup cap uses.
- **C — Streaming preserves validation logic**: `signing.loads`
  is per-row; iteration order doesn't matter; deleted rows don't
  affect ongoing iteration (Django's `.iterator()` uses a server-
  side cursor or fetchmany).

## Test plan

- **A — Single-task dispatch**: assert one `ImportTask` queued
  per library with all failed-import paths in `files_modified`.
- **B — Cap fires once on synthetic non-converging fixture**.
- **C — Memory ceiling**: validate 10,000 synthetic sessions
  under `tracemalloc`; assert peak < 50 MB (chunked) vs ~500 MB
  (pre-fix all-at-once).

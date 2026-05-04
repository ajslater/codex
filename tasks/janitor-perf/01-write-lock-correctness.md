# 01 — Acquire `db_write_lock` for cleanup / vacuum / backup writers

The headline correctness finding. **Ship first.**

## The bug

The integrity checks (`integrity/__init__.py`) correctly wrap
their writes in `with self.db_write_lock`. The cleanup writers
do not. Concrete sites:

| Site | File:line | Writes |
| --- | --- | --- |
| `cleanup_fks` | `cleanup.py:138-155` | DELETE across 25 FK models |
| `cleanup_custom_covers` | `cleanup.py:157-173` | DELETE on CustomCover |
| `cleanup_sessions` | `cleanup.py:175-208` | DELETE on Session |
| `cleanup_orphan_bookmarks` | `cleanup.py:210-220` | DELETE on Bookmark |
| `cleanup_orphan_settings` | `cleanup.py:222-235` | DELETE on Settings |
| `vacuum_db` | `vacuum.py:19-33` | `VACUUM` — exclusive at SQLite level |
| `backup_db` | `vacuum.py:35-53` | `VACUUM INTO` — heavy reader |

The codex daemon model serializes writers via the Python-level
`db_write_lock`, held by the importer for the whole duration of
an import. Without acquiring the same lock, the janitor can race
with an in-flight import.

## The race window

Concrete failure mode for `cleanup_fks` racing with the importer:

```
T+0   Importer chunk N starts:
        - bulk_create(Publisher, ["Indie Press LLC"], update_conflicts=True)
        - bulk_create(Imprint, [...], parent=Publisher)
        - bulk_create(Comic, [...], publisher=Publisher) ← not yet committed
T+1   Janitor's nightly fires; cleanup_fks starts.
T+2   Janitor queries Publisher for orphans (no inbound comic_set).
        - Importer's Publisher row is visible (auto-committed by chunk's
          atomic block on phase finish) but the referencing Comics
          haven't reached their atomic block yet.
        - Filter ``comic_set__isnull=True`` matches "Indie Press LLC".
T+3   Janitor DELETEs "Indie Press LLC".
T+4   Importer attempts to bulk_create the Comics referencing it
        → IntegrityError, the whole importer chunk rolls back.
        Comic data lost from this chunk; user must re-import.
```

This isn't theoretical. Codex polls libraries on a timer. If a
poll triggers an import around midnight (the janitor's default
schedule), the windows overlap.

For VACUUM the failure is louder:

```
T+0   Importer holds db_write_lock; mid-bulk_create.
T+1   Janitor calls vacuum_db. Acquires SQLite's exclusive lock.
T+2   Importer's next bulk_create hits "database is locked".
        Importer aborts mid-phase.
```

The Python-level `db_write_lock` exists precisely to prevent
SQLite-level lock contention from surfacing as user-facing
errors. Bypassing it loses that protection.

## Fix sketch

For each cleanup writer, wrap the body in `with self.db_write_lock`:

```python
def cleanup_fks(self) -> None:
    """Clean up unused foreign keys."""
    self.abort_event.clear()
    status = JanitorCleanupTagsStatus(0)
    try:
        self.status_controller.start(status)
        self.log.debug("Cleaning up orphan tags...")
        with self.db_write_lock:
            count = 1
            while count:
                count = self._cleanup_fks_one_level(status)
        level = "INFO" if status.complete else "DEBUG"
        self.log.log(level, f"Cleaned up {status.complete} unused tags.")
    finally:
        if self.abort_event.is_set():
            self.log.info("Cleanup tags task aborted early.")
        self.abort_event.clear()
        self.status_controller.finish(status)
```

Same shape for `cleanup_custom_covers`, `cleanup_sessions`,
`cleanup_orphan_bookmarks`, `cleanup_orphan_settings`,
`vacuum_db`, `backup_db`.

## Lock scope considerations

**How long should the lock be held?** As short as possible while
covering all writes. For each task:

- `cleanup_fks`: hold across the whole `while count:` loop —
  partial cleanups are valid but don't release the lock between
  passes (avoids window for an importer to re-create the orphan).
- `cleanup_custom_covers`: hold only across the DELETE, not the
  per-row stat() loop. The stat() phase is read-only and
  identifies the pks; release after collecting, re-acquire for
  the delete.
- `cleanup_sessions`: hold only across the DELETEs. The
  validation loop is read-only.
- `cleanup_orphan_bookmarks` / `cleanup_orphan_settings`: hold
  across the single DELETE. Microscopic.
- `vacuum_db`: hold across `VACUUM` only. PRAGMA optimize is
  cheap and can be inside or outside.
- `backup_db`: hold across `VACUUM INTO`. The OS-level rename of
  the previous backup file does not need the lock.

For `cleanup_custom_covers` specifically, the read/write split
matters: the per-cover filesystem stat is the slow part, and
holding `db_write_lock` for it would block the importer for
seconds-to-minutes on slow storage.

```python
def cleanup_custom_covers(self) -> None:
    """Clean up unused custom covers."""
    covers = CustomCover.objects.only("path")
    status = JanitorCleanupCoversStatus(0, covers.count())
    delete_pks = []
    try:
        self.status_controller.start(status)
        # Read-only phase: identify covers whose source files are gone.
        # Lock not held — importer may write freely.
        for cover in covers.iterator():
            if not Path(cover.path).exists():
                delete_pks.append(cover.pk)
            status.increment_complete()
        # Write phase: delete in one transaction under the lock.
        with self.db_write_lock:
            delete_qs = CustomCover.objects.filter(pk__in=delete_pks)
            count, _ = delete_qs.delete()
            status.complete = count
    finally:
        self.status_controller.finish(status)
```

The read-then-write split has a TOCTOU window: a cover could be
re-created between the stat and the delete. Acceptable —
worst case we delete a freshly-created cover, which is then
re-discovered by the next poll. No data loss.

## Cleanup coordination with VACUUM

Pre-existing concern: `vacuum_db` calls `PRAGMA optimize`,
`VACUUM`, then `PRAGMA wal_checkpoint(TRUNCATE)` in sequence.
SQLite docs: "VACUUM cannot be called within a transaction. It
also cannot be run on a database with open transactions." With
the importer's atomic blocks plus codex's WAL mode, this can
fail if any reader holds a snapshot.

The importer-perf series's PR #631 added `importer_pragmas()`
which fires `PRAGMA wal_checkpoint(TRUNCATE)` on import finish.
After an import finishes the WAL is empty. Janitor running after
a successful import is fine.

But: between import finish and janitor start, a browser request
might open a read transaction holding a snapshot. The lock
acquisition won't help with that — `db_write_lock` is for
writers, not readers.

**Mitigation**: log a warning and retry once if VACUUM fails.
Out of scope for this sub-plan (correctness first); document in
the implementation comment.

## Correctness invariants

- **No write semantics change**: every DELETE that ran before
  still runs; same rows are affected.
- **`abort_event` honored within lock**: each writer's existing
  `abort_event` checks remain, just inside the lock. If the user
  aborts mid-cleanup, the lock is released correctly via the
  context manager's `__exit__`.
- **Lock acquisition order**: codex's other writers (importer,
  bookmark daemon) acquire `db_write_lock` and never any other
  lock. Adding the janitor to this set doesn't introduce ordering
  hazards.

## Risks

- **Lock starvation**: a long cleanup_fks under the lock could
  block a polled import for tens of seconds. Acceptable — the
  alternative is data loss. The 5-pass cap from sub-plan 02
  bounds the worst case.
- **Backup duration**: `VACUUM INTO` on a 600k-comic DB can take
  minutes. The importer waits during this. Schedule expectation:
  backup runs at 4-6 am local; users should accept import lag.
- **Read-then-write split TOCTOU** in `cleanup_custom_covers`:
  documented above. Net effect is a no-op delete worst case.

## Suggested commit shape

One PR, one commit. Touches `cleanup.py` and `vacuum.py`. ~30
LOC change.

## Test plan

- **Read-write race**: integration test that fires a synthetic
  import + janitor concurrently. Without the fix, expect
  occasional IntegrityError. With the fix, expect zero.
- **Sequential ordering**: assert that `db_write_lock` is held
  exactly across the relevant DB statements (mock the lock,
  assert acquired before any DELETE/UPDATE/VACUUM SQL).
- **Wall clock**: cleanup_fks under no concurrent load should be
  ≤ 1.05× the pre-fix wall clock (lock acquisition itself is
  microseconds; only contention costs).

# 03 — `cleanup_custom_covers` filesystem stat batching

Self-contained in `cleanup.py:157-173`. The per-row `Path.exists()`
serializes filesystem I/O, which is fine on local SSD and painful
on NFS / SMB / cloud-mounted media.

## Hot path

```python
def cleanup_custom_covers(self) -> None:
    covers = CustomCover.objects.only("path")
    status = JanitorCleanupCoversStatus(0, covers.count())
    delete_pks = []
    try:
        self.status_controller.start(status)
        for cover in covers.iterator():
            if not Path(cover.path).exists():
                delete_pks.append(cover.pk)
            status.increment_complete()
        delete_qs = CustomCover.objects.filter(pk__in=delete_pks)
        count, _ = delete_qs.delete()
        ...
```

For each `CustomCover` row, `Path(cover.path).exists()` fires a
`stat(2)` system call. On a 1k-cover library hosted on:

| Storage | Per-stat | 1k covers | 10k covers |
| --- | --- | --- | --- |
| Local SSD | ~10 µs | ~10 ms | ~100 ms |
| Local HDD | ~100 µs | ~100 ms | ~1 s |
| NFS (LAN) | ~500 µs | ~500 ms | ~5 s |
| NFS (slow) | ~5 ms | ~5 s | ~50 s |
| SMB | ~10 ms | ~10 s | ~100 s |

Codex users frequently host comic libraries on NAS storage with
custom covers in subdirectories. The slow-NFS row is a real
scenario.

## Two-tier fix

### Tier A: directory grouping + scandir

Custom covers are typically organized hierarchically (one folder
per series, one cover per folder). Grouping covers by parent
directory lets us check existence via `os.scandir(parent)`
once per directory, then membership-test against an in-memory
set.

```python
from collections import defaultdict
import os

def cleanup_custom_covers(self) -> None:
    covers = CustomCover.objects.only("pk", "path")
    status = JanitorCleanupCoversStatus(0, covers.count())
    delete_pks = []
    # Group covers by their parent directory.
    by_dir: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for cover in covers.iterator():
        parent = os.path.dirname(cover.path)
        by_dir[parent].append((cover.pk, os.path.basename(cover.path)))
    try:
        self.status_controller.start(status)
        for parent, entries in by_dir.items():
            try:
                with os.scandir(parent) as it:
                    present = {entry.name for entry in it}
            except OSError:
                # Parent directory missing entirely — every cover in
                # this group is orphan.
                present = frozenset()
            for pk, basename in entries:
                if basename not in present:
                    delete_pks.append(pk)
                status.increment_complete()
            self.status_controller.update(status)
        # Delete under the lock (sub-plan 01).
        with self.db_write_lock:
            count, _ = CustomCover.objects.filter(pk__in=delete_pks).delete()
            status.complete = count
    finally:
        self.status_controller.finish(status)
```

scandir cost: O(directory size), one syscall + read. For a
directory with 100 cover files, scandir reads them all in ~one
NFS round-trip via READDIR. Beats 100 individual stat() calls.

For typical custom-cover layouts (1 cover per series folder),
this is identical-cost (one scandir per cover). For
many-covers-per-folder layouts, it's a big win. Worst case is
exactly the same as before.

### Tier B: thread pool for unavoidable per-cover stats

Some covers might not group well by parent dir (e.g., one cover
per arbitrary path). For those, stat() in a thread pool. I/O-
bound, threads work fine; no GIL contention on the syscalls.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

_COVER_STAT_WORKERS = 8

def _check_cover_exists(cover):
    return cover.pk, Path(cover.path).exists()

with ThreadPoolExecutor(max_workers=_COVER_STAT_WORKERS) as executor:
    futures = [executor.submit(_check_cover_exists, c) for c in covers]
    for future in as_completed(futures):
        pk, exists = future.result()
        if not exists:
            delete_pks.append(pk)
        status.increment_complete()
        self.status_controller.update(status)
```

Don't use both A and B together — Tier A is strictly better when
covers group cleanly, and Tier B is the fallback for the rare
cases where they don't. Either alone delivers the win.

**Recommendation: Tier A.** Simpler, no concurrency primitives,
and matches typical layout. If profiling reveals a layout where
Tier A doesn't help, add Tier B as a follow-up.

## Concurrency budget

If we go with Tier B (thread pool), worker count needs a cap:

- Local SSD: more workers don't help; one syscall per cover is
  the floor.
- NFS server with rate limit: 8-16 workers is a reasonable
  upper bound. Beyond that, the server starts queueing.
- Slow USB-attached disks: 1-4 workers max — a busy spindle
  serves stats slower than they queue.

Default 8 is conservative; expose as `IMPORTER_COVER_STAT_WORKERS`
for tuning.

## Correctness invariants

- **`Path.exists()` semantics preserved**: scandir's `entry.name`
  membership is equivalent to `Path(parent / name).exists()` for
  files. Symlinks are followed by both. Permission errors that
  hide a directory entry from scandir would have failed
  `Path.exists()` too.
- **Pre-existing TOCTOU**: a cover file created mid-stat would
  also race `Path.exists()`. No regression.
- **Empty-parent directory case**: scandir on a missing parent
  raises OSError; treat as "nothing exists in that directory" so
  every cover claiming a path under it gets deleted. Same as
  pre-fix per-cover behavior for missing parents.

## Risks

- **Permission errors on parent**: scandir requires read access
  on the directory. If the codex process can stat() individual
  files but can't readdir() the parent, scandir fails for the
  whole group while per-file stat would succeed. Mitigation:
  catch OSError per directory; fall back to per-file stat for
  that group only.
- **Symlink-as-directory**: scandir follows the symlink to read
  entries; behavior matches `Path.exists()`.
- **Very large directories**: scandir on a 100k-entry directory
  builds an in-memory set of ~10 MB. Fine.

## Suggested commit shape

One PR. Touches `cleanup.py`. ~80 LOC including the directory-
grouping helper. No new dependencies.

## Test plan

- **Functional equivalence**: synthetic fixture with covers in
  various states (present, missing, parent-missing, symlinked).
  Assert post-cleanup state matches pre-fix code byte-for-byte.
- **Performance regression test**: time a 5k-cover cleanup on a
  fixture where all covers share one parent directory. Pre-fix:
  5k stat() calls. Post-fix: 1 scandir + 5k set lookups. Expect
  10-100× wall-clock drop on remote storage.
- **Permission edge cases**: directory readable but not statable
  (the inverse of normal). Confirm fallback to per-file stat.

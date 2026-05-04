# Janitor perf + correctness — meta plan

`codex/librarian/scribe/janitor/` is small (~1200 LOC across 11
files) compared to the importer, but it runs nightly against the
entire DB and most of its work is unconditional table scans.
Several hot spots fire repeatedly across all 25 tag/group models;
a couple of latent correctness bugs put it at risk of stomping on
in-flight imports.

This is a meta-plan. The surface is small enough that one
investigative pass found the bulk of the issues; the sub-plans
below split them by concern (correctness first, perf wins second).

## Why this matters

The janitor's nightly task fires 14 sub-tasks (orphan folder
adoption, three integrity checks, FK cleanup, cover cleanup,
session/bookmark/settings cleanup, FTS sync + optimize, vacuum,
backup, cover orphan removal). On a 600k-comic library most of
these scan the full DB. A few bugs amplify: pathologically slow
filesystem ops, multi-pass loops without caps, and missing locks
that risk corrupting concurrent imports.

The substantive remaining work after the importer-perf series
(#628–#634) lives in two buckets:

1. **Correctness bugs** that only manifest under concurrent load —
   the kind that escape testing because they require a specific
   timing window. Several janitor cleanup tasks write to the DB
   without acquiring ``db_write_lock``, so a poll-driven import in
   progress can have its just-created Publisher/Imprint deleted as
   "orphan" before the import commits its referencing Comic.
2. **Per-row work amplified across full-table scans** — the kind
   the importer-perf series chased and largely won. Same flavor of
   N+1 / per-row-FS-stat / per-row-SQL exists here at smaller
   scale.

## Surface map

| Phase | File | LOC | What it does |
| ----- | ---- | --- | ------------ |
| Orchestration | `janitor.py` | 139 | Task dispatch, nightly task queueing |
| Tasks | `tasks.py` | 75 | Dataclass task definitions |
| Cleanup | `cleanup.py` | 235 | Orphan FK / cover / session / bookmark / settings deletion |
| Integrity | `integrity/__init__.py` | 124 | `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, FTS integrity |
| FK fix | `integrity/foreign_keys.py` | 208 | Resolve `foreign_key_check` violations into NULL/DELETE statements |
| Vacuum | `vacuum.py` | 53 | `PRAGMA optimize`, `VACUUM`, `VACUUM INTO` (backup) |
| Adopt | `adopt_folders.py` | 76 | Re-parent orphan folders via ComicImporter |
| Update | `update.py` | 91 | Codex software self-update |
| Failed | `failed_imports.py` | 26 | Re-queue failed-import paths for retry |
| Status | `status.py` | 162 | Status dataclasses |
| Schedule | `scheduled_time.py` | 13 | Midnight calculator |

## Confirmed concerns

### Correctness — concurrent writes without `db_write_lock`

`integrity/__init__.py` correctly wraps `foreign_key_check`,
`integrity_check`, `fts_rebuild`, and `fts_integrity_check` in
`with self.db_write_lock`. The cleanup writers do not:

- `cleanup_fks` (`cleanup.py:138`) — deletes orphan FK rows across
  25 models
- `cleanup_custom_covers` (`cleanup.py:157`) — deletes covers
- `cleanup_sessions` (`cleanup.py:175`) — deletes expired/corrupt
  sessions
- `cleanup_orphan_bookmarks` (`cleanup.py:210`) — deletes orphan
  bookmarks
- `cleanup_orphan_settings` (`cleanup.py:222`) — deletes orphan
  settings
- `vacuum_db` (`vacuum.py:19`) — `VACUUM` SQL holds an exclusive
  lock; concurrent writers hit "database is locked"
- `backup_db` (`vacuum.py:35`) — `VACUUM INTO` reads the entire DB

The importer holds `db_write_lock` for the duration of an import
(`librarian/worker.py`). If the janitor's nightly fires while a
poll-driven import is mid-run:

1. Importer creates Publisher "Indie Press LLC" in chunk 5, hasn't
   committed the Comics referencing it yet.
2. Janitor's `cleanup_fks` finds Publisher "Indie Press LLC" with
   no inbound `comic_set` refs (because the comics haven't
   committed) and deletes it.
3. Importer commits Comics referencing the now-deleted Publisher
   → IntegrityError, the whole importer chunk rolls back.

Detailed in [01-write-lock-correctness.md](./01-write-lock-correctness.md).
**Ship first.** Small change, biggest risk reduction.

### Perf — `cleanup_fks` runs O(M × P) full-table scans

`cleanup.py:130-148` `_cleanup_fks_one_level` walks all 25 FK
models, fires a `model.objects.filter(**filter_dict).distinct()`
per model. The outer `while count:` loop repeats until convergence.

Each filter is `{rev_rel}__isnull=True` over all reverse relations
— for a model with 10 incoming relations, that's a 10-LEFT-OUTER-JOIN
query on the model's table. SQLite plans these but they are not
free at scale.

For 25 models × P passes (typically 2-4), that's 50-100 full-table
scans per janitor run. On a 600k-comic library, the join-heavy
queries can run for tens of seconds each.

Plus: no convergence cap. Pathological data (a buggy importer state)
could in principle loop forever; the only escape is `abort_event`.

Detailed in [02-fk-cleanup.md](./02-fk-cleanup.md). Fix:
- Run cleanup_fks inside one `transaction.atomic` so a single
  multi-pass run is atomic.
- Add iteration cap (5 passes is more than enough for any
  realistic dependency graph).
- Optionally fold the per-model queries into a single pass via
  raw SQL `WITH` query against `sqlite_master` for the rev-rel
  list — moderate complexity, marginal win.

### Perf — `cleanup_custom_covers` per-row filesystem stat

`cleanup.py:157-173`:

```python
for cover in covers.iterator():
    if not Path(cover.path).exists():
        delete_pks.append(cover.pk)
```

For each `CustomCover` row, fires `Path(cover.path).exists()` —
serial filesystem stat. On NFS/SMB/cloud-mounted media (common for
codex on a NAS) each stat is ~1-50 ms. For a library with 5,000
custom covers that's 5-250 seconds of pure I/O wait.

Detailed in [03-cover-cleanup-fs.md](./03-cover-cleanup-fs.md). Fix:
- Group covers by parent directory and use `os.scandir(parent)`
  to batch-list files; check membership against in-memory sets.
- Or: parallelize via `concurrent.futures.ThreadPoolExecutor` —
  filesystem stat is I/O-bound, threads work fine.

### Perf — `fix_foreign_keys` per-rowid UPDATE/DELETE

`integrity/foreign_keys.py:142-158` `_fix_fk_violations`:

```python
for rowid, fk_cols in rows.items():
    if all_nullable:
        cursor.execute(f'UPDATE "{table_name}" SET ... WHERE rowid = %s', [rowid])
    else:
        cursor.execute(f'DELETE FROM "{table_name}" WHERE rowid = %s', [rowid])
```

One SQL round-trip per violating row. `PRAGMA foreign_key_check`
on a corrupted DB can return thousands of violations. Each is a
small SQL statement; round-trip overhead dominates.

Detailed in [04-fk-violations.md](./04-fk-violations.md). Fix:
batch by `(table_name, set-of-fk-cols, all-nullable-or-not)` into
`WHERE rowid IN (...)` form.

### Perf + correctness — assorted

`failed_imports.py:13-20` queues one `FSEventTask` per failed
import path. For a library with thousands of failed imports
(corrupt CBRs, etc.), the librarian queue receives thousands of
items processed serially.

`adopt_folders.py:48-76` has `while folders_left:` with no
iteration cap. If the importer fails to actually move folders
(permission errors, FS races), this can loop until the
abort_event is set externally.

`cleanup_sessions` (`cleanup.py:175-208`) iterates
`Session.objects.all()` to validate signatures. For users with
years of accumulated anonymous sessions this could be tens of
thousands of rows loaded into memory.

Detailed in [05-misc.md](./05-misc.md).

## Out of scope

- **`update.py` codex auto-update** — runs `pip install --upgrade`,
  not a perf concern; correctness is "did pip succeed?".
- **`scheduled_time.py`** — 13 LOC of datetime arithmetic.
- **`status.py`** — pure data classes.
- **The nightly task list itself** — order/composition is a
  product-design decision, not a perf concern.

## Sub-plans

Sub-plans are independent and can ship in any order. Suggested
order is by impact, with correctness first:

1. **[01-write-lock-correctness.md](./01-write-lock-correctness.md)** —
   Wrap cleanup / vacuum / backup writers in `with
   self.db_write_lock`. Eliminates the importer-vs-janitor race.
   Single-file diff, ~30 LOC.
2. **[02-fk-cleanup.md](./02-fk-cleanup.md)** —
   `cleanup_fks` transaction wrap + iteration cap + log when cap
   hit. ~40 LOC.
3. **[04-fk-violations.md](./04-fk-violations.md)** —
   Batch the per-rowid UPDATE/DELETE in `fix_foreign_keys`. ~50
   LOC.
4. **[03-cover-cleanup-fs.md](./03-cover-cleanup-fs.md)** —
   Group cover stat() by parent dir + scandir, or thread-pool
   parallelize. ~80 LOC.
5. **[05-misc.md](./05-misc.md)** —
   Failed-import re-queue batching, session validation chunking,
   adopt-folders iteration cap. ~60 LOC across three small fixes.

## Methodology

For each finding:

1. **Reproduce in a test fixture** where possible (concurrent
   importer + janitor race is hard to reproduce reliably; rely on
   logical reasoning + code review).
2. **Apply the fix in isolation** — one sub-plan = one PR.
3. **Verify correctness via diff against pre-fix DB state** for
   non-trivial changes — e.g., for FK cleanup, dump
   `(model, count)` pairs before and after a janitor run on a
   test fixture and confirm equality.

## Correctness invariants to preserve

- **`db_write_lock` semantics**: only one Python-level writer at a
  time. The janitor must respect this boundary.
- **Cascading delete semantics**: `cleanup_fks`'s convergence
  loop relies on the property that deleting an orphan can produce
  more orphans (e.g., delete a Credit → its CreditPerson and
  CreditRole may now be orphan). Any rewrite must preserve this.
- **`PRAGMA foreign_key_check` accuracy**: SQLite only reports
  violations for `FOREIGN KEYS` declared with `PRAGMA
  foreign_keys=ON`. Codex's connection has this on. ✓
- **`VACUUM` blocks all readers and writers** — the steady-state
  PRAGMAs include WAL mode but VACUUM is the exception. The fix
  is the lock acquisition (sub-plan 01), not skipping VACUUM.

## Risks

- **Long-held `db_write_lock` during VACUUM** — VACUUM on a
  multi-GB DB can take minutes. While held, all writers (importer,
  bookmark daemon, scribe) wait. Not a regression — current
  behavior is "concurrent writes hit `database is locked`",
  which is worse. Sub-plan 01 makes the wait explicit and
  serializes cleanly.
- **Cover stat() parallelism on slow FS** — running 32 threads
  against an NFS share with a tight rate limit could trigger
  server-side throttling. Cap concurrency to a small number
  (e.g., 8) and document.
- **FK cleanup iteration cap might fire on legitimate deep
  cascades** — typical FK graphs converge in 2-3 passes. A cap of
  10 is generous. If it fires, log loud (warn) so the user can
  investigate.

## References

- `codex/librarian/worker.py` — `WorkerStatusAbortableBase` +
  `db_write_lock` semantics
- `codex/librarian/scribe/importer/pragmas.py` — importer's
  scoped PRAGMA pattern (potentially reusable for vacuum)
- PR #631 (importer transaction.atomic) — reference for
  `with transaction.atomic()` usage
- PR #634 (importer chunked apply) — reference for memory-bounded
  chunking patterns

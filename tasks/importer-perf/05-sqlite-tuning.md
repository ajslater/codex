# 05 — SQLite tuning for bulk imports

The current global PRAGMA set
(`settings/__init__.py:430-436`) is well-tuned for the **steady
state** — concurrent reads while a single writer drips changes
in. That's the right shape for the browser. It's a poor shape for
a 600k-comic bulk import, where the writer dominates and read
concurrency is irrelevant for the duration of the run.

This sub-plan adds an **importer-scoped PRAGMA override** plus
explicit transaction batching, leaving the steady-state config
untouched.

## Current global PRAGMAs

```python
_SQLITE_PRAGMAS = (
    "PRAGMA journal_mode=wal;"
    "PRAGMA synchronous=NORMAL;"
    "PRAGMA temp_store=MEMORY;"
    "PRAGMA mmap_size=268435456;"   # 256 MiB
    "PRAGMA cache_size=-64000;"      # 64 MiB
)
```

These are good defaults. The points below are *additive*, fired
once at import start and reverted at finish.

## Hot path: every `bulk_create` / `bulk_update` is its own transaction

`grep -rn "transaction.atomic" codex/librarian/scribe/` returns
**zero hits**. Every Django ORM write call inside the importer
runs in autocommit mode — meaning SQLite fsyncs the WAL after
every batch.

For a fresh 600k-comic import, the create + link + update phases
fire roughly:

| Phase | Approx batches |
| --- | --- |
| Create FKs (Publisher → Volume + StoryArcNumber + Credit + Identifier) | ~50 |
| Create Comics | ~600 (1k batch size × 600k comics) |
| Link M2Ms (14 fields × N batches) | ~200 |
| Update Comics | ~1500 (400 batch size × 600k) |
| Total | **~2300 commits** |

Under `synchronous=NORMAL` each commit is one fsync of the WAL
file. On a typical SATA SSD that's ~5-10ms per fsync, so the
fsync cost alone is **15-25 seconds of pure wait** on the import
critical path.

Wrap each phase in a single `transaction.atomic()`:

```python
# codex/librarian/scribe/importer/importer.py
_METHODS = (
    ("init_apply", _init_apply),
    ("move_and_modify_dirs", _move_and_modify_dirs),
    ("read", _read),
    ("query", _query),
    ("create_and_update", _create_and_update),  # ← wrap this
    ("link", _link),                             # ← and this
    ("fail_imports", _fail_imports),
    ("delete", _delete),
    ("full_text_search", _full_text_search),
)
```

```python
def _create_and_update(self) -> None:
    from django.db import transaction
    with transaction.atomic():
        # Existing body unchanged.
        ...
```

The fsync count collapses from ~2300 to ~5 (one per wrapped
phase). Throughput limited only by raw write speed and bulk SQL
generation overhead.

### Risk: long-running write transaction blocks readers

Under WAL, *readers* aren't blocked by a writer holding the write
lock — they read from the snapshot at the start of their
transaction. So wrapping the importer phases in `atomic` doesn't
prevent the browser from serving pages.

What it **does** prevent: any other writer (the bookmark daemon,
the cover daemon writing thumbnails, the scribe daemon's own
search-sync phase if it's a separate transaction) from making
progress while the lock is held. The codex daemon model already
serializes writes via `db_write_lock` (see
`librarian/worker.py:21-29`), so this is a non-issue in practice
— the importer already has the write lock for the whole run.

### Risk: `transaction.atomic` rolls back on uncaught exception

The current shape lets a failing batch leave previously-committed
batches in place. The atomic wrap means a single bad batch
rolls back the entire phase. Two mitigations:

1. The importer already catches per-row failures and stuffs them
   into `FailedImport` rows in the `fail_imports` phase. Phase-
   level catastrophic failure is rare and probably *should* roll
   back to keep the DB consistent.
2. If finer-grained recovery is wanted, use `transaction.atomic`
   with `savepoint=True` per inner batch:

```python
with transaction.atomic():  # outer phase
    for batch in batches:
        try:
            with transaction.atomic(savepoint=True):
                bulk_create(batch, ...)
        except IntegrityError:
            self.log.exception("batch failed, continuing")
```

Savepoints are cheap on SQLite (no fsync). Verify by reading
existing `_bulk_create_models` exception flow before adopting.

## Importer-scoped PRAGMA override

A second cursor knob: bump cache aggressively for the duration of
the import, then revert.

```python
# codex/librarian/scribe/importer/init.py
_IMPORT_PRAGMAS = (
    # 512 MiB page cache — typical 600k-comic working set fits
    # easily, eliminating page-cache misses during the link phase.
    "PRAGMA cache_size=-524288;"
    # Defer WAL checkpoints until import finish. Default is every
    # 1000 pages (~4 MiB) which fires hundreds of times during a
    # large import, each one stalling the writer briefly.
    "PRAGMA wal_autocheckpoint=0;"
    # Optionally:
    # PRAGMA synchronous=OFF — faster but loses durability of the
    # *entire* import on power-cut, not just the last txn. Skip
    # unless we add a "verify and re-import on startup" mechanism.
)
_RESTORE_PRAGMAS = (
    "PRAGMA cache_size=-64000;"
    "PRAGMA wal_autocheckpoint=1000;"
)

def _apply_import_pragmas(self) -> None:
    with connection.cursor() as cursor:
        cursor.executescript(_IMPORT_PRAGMAS)

def _restore_pragmas_and_checkpoint(self) -> None:
    with connection.cursor() as cursor:
        cursor.executescript(_RESTORE_PRAGMAS)
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        cursor.execute("PRAGMA optimize")  # update stats post-import
```

Wire into `init_apply` (start) and `finish` (end). The `PRAGMA
optimize` at finish is important — after inserting hundreds of
thousands of rows, SQLite's query planner uses outdated
statistics until the next `ANALYZE` or `PRAGMA optimize`. The
janitor runs this on its schedule; firing it inline after a big
import shortens the window of bad query plans.

### `cache_size` ceiling

`-524288` = 512 MiB. On a 1 GiB-RAM Raspberry Pi this is
aggressive. Read the resident set at import start and back off if
total RAM < 2 GiB. Or expose as a config knob:

```python
IMPORTER_SQLITE_CACHE_KB = get_int(
    CODEX_CONFIG, "importer.sqlite_cache_kb", default=524288
)
```

Default of 512 MiB matches the existing `cache_size` mental model
(negative = KiB).

### `wal_autocheckpoint=0` interaction with crash recovery

With `wal_autocheckpoint=0`, the WAL grows unbounded until
`PRAGMA wal_checkpoint` is fired. For a 600k-comic import the
WAL might reach a few hundred MB. On crash, recovery replays the
WAL — which is fine, just slower than a checkpointed DB.

Force `wal_checkpoint(TRUNCATE)` at finish (already in
`_restore_pragmas_and_checkpoint` above).

## Why not `PRAGMA locking_mode=EXCLUSIVE`?

Tempting — exclusive locking mode lets SQLite skip
acquire/release of the file lock per transaction, and is a real
win on slow filesystems. But:

1. Codex's `db_write_lock` already serializes writers at the
   Python level, so the OS-lock contention is zero.
2. Exclusive mode prevents *other processes* (e.g. an `sqlite3`
   CLI session, a backup script, codex's own backup process)
   from reading the DB until the importer connection closes.
   That's a bigger UX regression than the perf win is worth.

Skip.

## Why not `journal_mode=MEMORY` or `OFF`?

`MEMORY` keeps the rollback journal in RAM — fast, but a crash
mid-import corrupts the DB unrecoverably. We're not Redis.

`OFF` turns off the rollback journal entirely — same risk profile
plus no transaction support.

Skip both. WAL is correct for this workload.

## Composite knob: connection reuse during the import

Django's `CONN_MAX_AGE=600` recycles connections every 10
minutes. A 600k-comic import takes ~30+ minutes; mid-run
reconnect re-fires `_SQLITE_PRAGMAS`, **resetting our import-
scoped cache_size and wal_autocheckpoint=0 overrides**.

Two fixes:

1. **Hold a long-lived cursor** from the importer thread for the
   duration of the run. Django's `connection` is thread-local, so
   keeping a reference prevents recycle. (Verify against
   Django 6's connection pool semantics — there's been churn.)
2. **Re-apply `_IMPORT_PRAGMAS` on every `connection_created`
   signal** for the duration of the import:

```python
from django.db.backends.signals import connection_created

def _on_connect(sender, connection, **kwargs):
    with connection.cursor() as cursor:
        cursor.executescript(_IMPORT_PRAGMAS)

# In init_apply:
connection_created.connect(_on_connect)
# In finish:
connection_created.disconnect(_on_connect)
```

Option 2 is robust against any reconnect, including ones we
don't trigger. Prefer it.

## Correctness invariants

- **Atomicity per phase**: wrapping a phase in `transaction.atomic`
  does not change visibility of intermediate writes to the same
  process — Django's ORM still sees uncommitted rows within the
  same transaction. Only externally visible behavior changes.
- **PRAGMA scoping**: `cache_size` and `wal_autocheckpoint` are
  per-connection, so the override applies only to the importer's
  connection. Browser / API connections keep the steady-state
  values.
- **`PRAGMA optimize` is read-only-ish**: it may run `ANALYZE` on
  tables it deems stale. No data mutation, but it acquires the
  write lock briefly. Run it before releasing `db_write_lock`.
- **WAL size after import**: forcing `wal_checkpoint(TRUNCATE)`
  at finish leaves the WAL file ~empty. Subsequent reader/writer
  cadence is identical to pre-import.

## Risks

- **`PRAGMA optimize` cost on huge tables**: on a freshly-imported
  600k-row Comic table, optimize may decide to ANALYZE, which is
  O(n log n). Could add seconds to import finish. Worth measuring;
  if too costly, skip and let the janitor's scheduled VACUUM run
  it.
- **`wal_autocheckpoint=0` on disk-full**: WAL growth without
  checkpoint can fill the disk. For a worst-case 600k import the
  WAL maxes ~500 MB; disk-full mid-import on a near-full system
  would corrupt nothing (SQLite handles it cleanly) but would
  abort the import. Mention in user docs.
- **`connection_created` signal scope**: signals fire across all
  connections in the process. The bookmark thread, cover thread,
  etc. would also pick up the import PRAGMAs if they connect
  during the import. Since `db_write_lock` serializes writers,
  they're idle anyway, but verify that read-only daemons (e.g.
  the notifier) don't connect during the window. If they do,
  they'd just get a bigger cache — no correctness issue.
- **Per-phase atomic and `bulk_create(update_conflicts=True)`**:
  `update_conflicts` uses ON CONFLICT DO UPDATE under the hood.
  Atomic wrap is fine. Verified by reading Django ORM source
  (`db/models/sql/compiler.py`).

## Suggested commit shape

Two commits, one PR:

1. `importer: wrap create/link/update phases in transaction.atomic`
   (~30 LOC across `importer.py`, no behavior change beyond fsync
   coalescing)
2. `importer: scoped PRAGMAs and post-import checkpoint`
   (~70 LOC adding init/finish hooks, signal handler, and the
   PRAGMA strings)

Total ~100 LOC. Touches `importer.py`, `init.py`, `finish.py`,
and adds a small `pragmas.py` module.

## Expected speedup

Hard to predict precisely without measurement. Order-of-magnitude
estimate for a fresh 600k-comic import:

| Optimization | Time saved |
| --- | --- |
| Phase-level `atomic()` (collapsing 2300 fsyncs to ~5) | 15-25 s |
| 512 MiB cache (eliminating page misses on link phase) | 30-90 s |
| `wal_autocheckpoint=0` (no mid-import checkpoint stalls) | 5-15 s |
| **Combined** | **~1-2 minutes** off a 30-min import |

Not the headline win (that's batch-01 link phase), but cheap and
cumulative.

## Test plan

- **Atomic phase rollback**: inject a synthetic IntegrityError
  mid-create-phase. Assert the entire phase rolls back (no
  partial Volume rows). Verify FailedImport rows are still
  written (those happen in the `fail_imports` phase, outside the
  atomic block).
- **PRAGMA reapplication**: simulate a connection drop mid-import
  (e.g. close the SQLite connection out from under Django) and
  assert the next cursor inherits `cache_size=-524288`.
- **WAL checkpoint at finish**: after a 1k-comic test import,
  assert `Path('codex.sqlite3-wal').stat().st_size` is < 4 KiB
  (one WAL frame post-truncate).
- **Wall clock**: 10k-comic dev fixture, time the
  `create_and_update` phase before/after. Expect 10-20% drop.
- **Stats freshness**: after a large insert + `PRAGMA optimize`,
  query plan for a typical browser page should match the planner
  output post-VACUUM. Compare with `EXPLAIN QUERY PLAN`.

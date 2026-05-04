# 02 — `cleanup_fks` transaction wrap + iteration cap

Self-contained in `cleanup.py:138-155`. After the write-lock fix
from sub-plan 01, this tightens semantics and adds a safety cap.

## Hot path

```python
def cleanup_fks(self) -> None:
    self.abort_event.clear()
    status = JanitorCleanupTagsStatus(0)
    try:
        self.status_controller.start(status)
        self.log.debug("Cleaning up orphan tags...")
        count = 1
        while count:
            # Keep churning until we stop finding orphan tags.
            count = self._cleanup_fks_one_level(status)
        ...
```

`_cleanup_fks_one_level` walks all 25 FK models and fires a
`filter(...).delete()` per model. Each `.delete()` is its own
implicit transaction.

## Issues

### No iteration cap

`while count:` runs until convergence with no upper bound. For
correctly-formed data this converges in 2-3 passes. For
pathological data (a corrupt DB where deletes don't actually
remove rows, or a buggy reverse-rel map) this loops indefinitely
until `abort_event` is set externally.

### No transaction wrap

Each `.delete()` is auto-committed. If aborted mid-loop:
- Some models cleaned up
- Others not
- DB state is consistent (orphans are still orphans, just more
  of them than before)
- But: the convergence guarantee is partially broken — next run
  picks up where this one left off, which is fine.

The risk is more subtle: if the per-model deletes interleave with
another writer (after sub-plan 01 lands, this is impossible; but
defense-in-depth is cheap), wrapping the whole loop in
`transaction.atomic` makes the whole cleanup all-or-nothing.

### Per-model deletes generate many small queries

25 models × P passes = 50-100 small DELETE statements per janitor
run. Each is a separate round-trip. Bundling them under one
`atomic` doesn't reduce SQL volume but coalesces fsyncs.

## Fix sketch

```python
_FK_CLEANUP_MAX_PASSES = 10

def cleanup_fks(self) -> None:
    """Clean up unused foreign keys."""
    self.abort_event.clear()
    status = JanitorCleanupTagsStatus(0)
    try:
        self.status_controller.start(status)
        self.log.debug("Cleaning up orphan tags...")
        with self.db_write_lock, transaction.atomic():
            for pass_num in range(_FK_CLEANUP_MAX_PASSES):
                if self.abort_event.is_set():
                    return
                count = self._cleanup_fks_one_level(status)
                if not count:
                    break
            else:
                self.log.warning(
                    f"FK cleanup hit {_FK_CLEANUP_MAX_PASSES}-pass cap "
                    "without converging — investigate the reverse-relation "
                    "map or the data graph."
                )
        level = "INFO" if status.complete else "DEBUG"
        self.log.log(level, f"Cleaned up {status.complete} unused tags.")
    finally:
        if self.abort_event.is_set():
            self.log.info("Cleanup tags task aborted early.")
        self.abort_event.clear()
        self.status_controller.finish(status)
```

The `for...else` idiom: `else` fires only if the loop completes
without `break`. Cleanly expresses "we hit the cap; warn".

## Why 10 passes?

Empirical guess. Codex's FK graph depth is bounded by the
hierarchy:

```
Identifier → Publisher → Imprint → Series → Volume → Comic
                                        ↘ Credit ↗
                                        ↘ StoryArcNumber → StoryArc
```

In any deletion order, a fully-orphaned chain converges in at
most ~5 passes. 10 doubles that for safety. If a real DB ever
fails to converge in 10, that's a data integrity bug worth
investigating, not a fix-by-bumping-the-cap problem.

## Optional: collapse to a single SQL pass

The plan's secondary item: replace the Python-side multi-pass
loop with a single SQL `WITH RECURSIVE` query. SQLite supports
recursive CTEs, and the orphan-detection logic is mechanical:

```sql
WITH RECURSIVE orphans(table_name, pk) AS (
    -- Base case: rows with no inbound refs
    SELECT 'codex_publisher', id FROM codex_publisher
        WHERE id NOT IN (SELECT publisher_id FROM codex_imprint WHERE publisher_id IS NOT NULL)
        AND id NOT IN ...
    -- Recursive: rows whose only refs are themselves orphans
    UNION ALL
    SELECT ...
)
```

Generating this query from the rev-rel map is doable but
non-trivial and SQLite-specific. Skip for now — the Python
loop is fine after the cap.

## Correctness invariants

- **Convergence semantics preserved**: the loop still runs to
  exhaustion (or to the cap), so the same orphans get deleted.
- **Atomic rollback on exception**: if a DELETE fails mid-loop,
  the entire cleanup rolls back to pre-cleanup state. Acceptable
  — the alternative is "some models cleaned up, some not", which
  is also valid but less predictable.
- **`abort_event` still works**: checked at the top of each pass.
  Abort during a pass lets that pass complete, then exits.
- **`status.complete` accumulates correctly**: `_cleanup_fks_one_level`
  already increments status.complete per model. Atomic wrap
  doesn't change that — even on rollback the status counter is
  Python-side and reflects what was attempted.

## Risks

- **Lock held longer**: with sub-plan 01's `db_write_lock`, the
  atomic wrap means the lock spans all passes. Worst case is
  ~10 passes × ~25 models × ~ms = single-digit seconds of lock
  hold. Acceptable.
- **`atomic` rolls back on uncaught exception**: by design.
  Reduces partial-cleanup confusion.
- **Cap warning on legitimate convergence**: a graph that
  legitimately needs more than 10 passes is exotic. The warn-and-
  continue pattern is right; user can re-run the janitor
  manually if needed.

## Suggested commit shape

One PR, one commit. Builds on sub-plan 01 (which adds the
`with self.db_write_lock` wrapper). ~40 LOC change to `cleanup.py`.

## Test plan

- **Convergence in N passes**: synthetic fixture with a 5-deep
  orphan chain. Assert cleanup converges in ≤ 5 passes and
  doesn't fire the cap warning.
- **Cap fires loudly**: synthetic fixture where deletes don't
  actually remove rows (mock the model). Assert the warning fires
  exactly once.
- **Atomic rollback**: inject an IntegrityError mid-loop. Assert
  no partial state survives.
- **Wall clock**: 600k-comic DB with no orphans should run
  cleanup in ≤ 1s (one pass, returns 0, exits).

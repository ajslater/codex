# 04 — Batch per-rowid UPDATE/DELETE in `fix_foreign_keys`

`integrity/foreign_keys.py:142-158` does one SQL statement per
violating row. `PRAGMA foreign_key_check` on a corrupt DB can
return thousands of violations; round-trip overhead dominates.

## Hot path

```python
for table_name, rows in violations.items():
    fix_comic_pks |= _collect_comic_ids_for_table(...)

    for rowid, fk_cols in rows.items():
        all_nullable = all(nullable for _, nullable in fk_cols)

        if all_nullable:
            set_clauses = ", ".join(f'"{col}" = NULL' for col, _ in fk_cols)
            cursor.execute(
                f'UPDATE "{table_name}" SET {set_clauses} WHERE rowid = %s',
                [rowid],
            )
            nulled += cursor.rowcount
        else:
            cursor.execute(
                f'DELETE FROM "{table_name}" WHERE rowid = %s',
                [rowid],
            )
            deleted += cursor.rowcount
```

For each violating row: one round-trip. On a DB that's been
unlucky enough to have FK corruption, "thousands of violations"
isn't unrealistic (e.g., a power-cut during a bulk delete).

## Why this is N+1

The pattern shape:
- Same SQL template across rows (UPDATE or DELETE)
- Different rowids per row
- For UPDATE: same SET clauses per (table, fk_col_set)

Bunching by `(table, fk_col_set, all_nullable)` produces
`WHERE rowid IN (...)` queries — one per group instead of one
per row.

## Fix sketch

```python
from collections import defaultdict

def _fix_fk_violations(
    cursor, violations: dict[str, dict[int, list[tuple[str, bool]]]]
) -> tuple[int, int, set[int]]:
    """Null or delete rows with broken foreign keys.

    Bunches per-row fixes by (table, fk_col_set, all_nullable) so
    each batch is one ``WHERE rowid IN (...)`` query rather than
    one round-trip per row.
    """
    nulled = 0
    deleted = 0
    fix_comic_pks: set[int] = set()

    for table_name, rows in violations.items():
        fix_comic_pks |= _collect_comic_ids_for_table(
            cursor, table_name, set(rows.keys())
        )

        # Group rows by (frozen fk_col_set, all_nullable).
        groups: dict[tuple, list[int]] = defaultdict(list)
        for rowid, fk_cols in rows.items():
            cols = tuple(sorted(col for col, _ in fk_cols))
            all_nullable = all(nullable for _, nullable in fk_cols)
            groups[(cols, all_nullable)].append(rowid)

        for (cols, all_nullable), rowids in groups.items():
            # Stay under SQLite's 32766-variable cap.
            for start in range(0, len(rowids), _SQLITE_MAX_VARS):
                batch = rowids[start : start + _SQLITE_MAX_VARS]
                placeholders = ",".join(["%s"] * len(batch))
                if all_nullable:
                    set_clauses = ", ".join(f'"{col}" = NULL' for col in cols)
                    cursor.execute(
                        f'UPDATE "{table_name}" SET {set_clauses} '  # noqa: S608
                        f"WHERE rowid IN ({placeholders})",
                        batch,
                    )
                    nulled += cursor.rowcount
                else:
                    cursor.execute(
                        f'DELETE FROM "{table_name}" '  # noqa: S608
                        f"WHERE rowid IN ({placeholders})",
                        batch,
                    )
                    deleted += cursor.rowcount

    return nulled, deleted, fix_comic_pks
```

Where `_SQLITE_MAX_VARS = 32000` (leaves headroom under SQLite's
32766 variable cap).

## Query count

For a hypothetical 10,000-violation DB across 5 tables:

| | per call |
| --- | --- |
| **Before** | 10,000 SQL statements |
| **After** | ~5-10 SQL statements (one per table×col-set×nullable group, each batched at 32k vars) |

Each statement does the same work in SQL terms — same rows
updated/deleted. The win is round-trip overhead.

## Correctness invariants

- **Same rows updated/deleted as before**: `WHERE rowid IN (...)`
  with the same set of rowids hits the same rows as N individual
  `WHERE rowid = ?` statements.
- **`cursor.rowcount` accumulates correctly**: with batched
  statements, `rowcount` returns rows affected by that statement.
  Sum across batches still equals total rows affected.
- **Mixed-nullable rows in same table**: a table can have rows
  whose violations are all-nullable AND rows whose violations
  include a non-nullable column. The grouping handles this — the
  nullable group nulls, the non-nullable group deletes. Same
  per-row decision as before.
- **`_collect_comic_ids_for_table`** runs once per table before
  the grouping; comics-to-update set is unchanged.

## Risks

- **Variable count**: stay well under 32766. 32000 leaves headroom
  for SQLite internal use.
- **`UPDATE ... SET col=NULL ... WHERE rowid IN (...)`**: SQLite
  applies the SET to every matching row. Same as N individual
  UPDATEs.
- **Partial application on error**: if a batch's UPDATE fails
  (e.g., constraint violation), the whole batch's rows are
  unaffected. Same as N individual statements where the failure
  point would split partial-success. Net behavior is "all or
  nothing per batch", which is safer.

## Suggested commit shape

One PR. Touches `integrity/foreign_keys.py`. ~50 LOC change. The
helper logic stays the same; only `_fix_fk_violations` is
restructured.

## Test plan

- **Functional equivalence**: synthetic DB with 100 violations
  across 3 tables (mix of nullable / non-nullable columns).
  Assert post-fix DB state matches the per-row code's output
  byte-for-byte.
- **Variable cap**: synthetic DB with 50,000 violations in one
  table. Assert no `too many SQL variables` error; batching
  splits at 32000.
- **`cursor.rowcount` totals match**: assert sum of batch
  rowcounts equals number of input rowids.

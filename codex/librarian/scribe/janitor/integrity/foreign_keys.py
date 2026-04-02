"""Database integrity checks and remedies."""

# Uses app.get_model() because functions may also be called before the models are ready on startup.
from typing import TYPE_CHECKING

from django.apps import apps
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models.functions import Now

if TYPE_CHECKING:
    from django.db.models.manager import BaseManager

    from codex.models.comic import Comic


def _get_fk_column_name(cursor, table_name: str, fkid: int) -> str | None:
    """Resolve fkid to the child column name via PRAGMA foreign_key_list."""
    cursor.execute(f'PRAGMA foreign_key_list("{table_name}")')
    # Columns: id, seq, table, from, to, on_update, on_delete, match
    for row in cursor.fetchall():
        if row[0] == fkid and row[1] == 0:
            return row[3]  # 'from' = child column name
    return None


def _is_column_nullable(cursor, table_name: str, column_name: str) -> bool:
    """Check if a column allows NULL via PRAGMA table_info."""
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    # Columns: cid, name, type, notnull, dflt_value, pk
    for row in cursor.fetchall():
        if row[1] == column_name:
            return row[3] == 0  # notnull=0 means nullable
    return False


def _collect_comic_ids_for_table(cursor, table_name: str, rowids: set) -> set:
    """Collect comic PKs that need re-indexing after FK fixes."""
    if table_name == "codex_comic":
        # rowid == pk for standard Django integer-PK models.
        return set(rowids)
    # For m2m through tables or other tables with a comic_id column.
    try:
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        has_comic_id = any(row[1] == "comic_id" for row in cursor.fetchall())
    except Exception:
        return set()
    if not has_comic_id:
        return set()
    placeholders = ",".join(["%s"] * len(rowids))
    cursor.execute(
        f'SELECT comic_id FROM "{table_name}" WHERE rowid IN ({placeholders})',  # noqa: S608
        sorted(rowids),
    )
    return {row[0] for row in cursor.fetchall() if row[0] is not None}


def _mark_comics_for_update(fix_comic_pks, log) -> None:
    """Mark comics with altered foreign keys for update."""
    if not fix_comic_pks:
        return
    comic_model: type[Comic] = apps.get_model(app_label="codex", model_name="comic")  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
    outdated_comics: BaseManager[Comic] = comic_model.objects.filter(
        pk__in=fix_comic_pks
    ).only("stat", "updated_at")
    if not outdated_comics:
        return

    update_comics = []
    now = Now()
    for comic in outdated_comics:
        stat_list = comic.stat
        if not stat_list:
            continue
        stat_list[8] = 0.0
        comic.stat = stat_list  # pyright: ignore[reportAttributeAccessIssue]
        comic.updated_at = now
        update_comics.append(comic)

    if update_comics:
        count = comic_model.objects.bulk_update(
            update_comics, fields=["stat", "updated_at"]
        )
        log.info(f"Marked {count} comics with bad relations for update by poller.")


def _group_fk_violations(
    cursor, results, log
) -> dict[str, dict[int, list[tuple[str, bool]]]]:
    """
    Resolve raw PRAGMA foreign_key_check rows into grouped violations.

    Returns {table: {rowid: [(column_name, nullable), ...]}}.
    """
    col_info_cache: dict[tuple[str, int], tuple[str | None, bool]] = {}
    violations: dict[str, dict[int, list[tuple[str, bool]]]] = {}

    for table_name, rowid, _parent, fkid in results:
        cache_key = (table_name, fkid)
        if cache_key not in col_info_cache:
            fk_col = _get_fk_column_name(cursor, table_name, fkid)
            nullable = (
                _is_column_nullable(cursor, table_name, fk_col) if fk_col else False
            )
            col_info_cache[cache_key] = (fk_col, nullable)

        fk_col, nullable = col_info_cache[cache_key]
        if not fk_col:
            log.warning(
                f"Could not resolve FK column for {table_name} fkid={fkid}, skipping"
            )
            continue

        violations.setdefault(table_name, {}).setdefault(rowid, []).append(
            (fk_col, nullable)
        )

    return violations


def _fix_fk_violations(
    cursor, violations: dict[str, dict[int, list[tuple[str, bool]]]]
) -> tuple[int, int, set[int]]:
    """
    Null or delete rows with broken foreign keys.

    For each violation:
    - If all bad FK columns on the row are nullable: NULL them.
    - Otherwise: DELETE the row.

    Returns (nulled_count, deleted_count, fix_comic_pks).
    """
    nulled = 0
    deleted = 0
    fix_comic_pks: set[int] = set()

    for table_name, rows in violations.items():
        # Collect comic_ids before we delete any rows.
        fix_comic_pks |= _collect_comic_ids_for_table(
            cursor, table_name, set(rows.keys())
        )

        for rowid, fk_cols in rows.items():
            all_nullable = all(nullable for _, nullable in fk_cols)

            if all_nullable:
                set_clauses = ", ".join(f'"{col}" = NULL' for col, _ in fk_cols)
                cursor.execute(
                    f'UPDATE "{table_name}" SET {set_clauses} WHERE rowid = %s',  # noqa: S608
                    [rowid],
                )
                nulled += cursor.rowcount
            else:
                cursor.execute(
                    f'DELETE FROM "{table_name}" WHERE rowid = %s',  # noqa: S608
                    [rowid],
                )
                deleted += cursor.rowcount

    return nulled, deleted, fix_comic_pks


def fix_foreign_keys(log) -> None:
    """
    Fix all foreign key violations using raw SQL.

    Uses PRAGMA foreign_key_check to find violations, then for each bad row
    nulls the FK column if nullable, or deletes the row if not.

    Operates entirely via raw SQL and rowid so it works for all tables
    including third-party ones (e.g. authtoken_token) without requiring
    ORM model resolution.
    """
    connection = connections[DEFAULT_DB_ALIAS]
    connection.prepare_database()
    try:
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            cursor.execute("PRAGMA foreign_key_check")
            results = cursor.fetchall()

            if not results:
                log.success("Database passed foreign key check.")
                return

            log.warning(
                f"Found {len(results)} foreign key violations. Attempting fix..."
            )
            log.debug(results)

            violations = _group_fk_violations(cursor, results, log)
            nulled, deleted, fix_comic_pks = _fix_fk_violations(cursor, violations)

            if nulled:
                log.info(
                    f"Nulled bad foreign keys on {nulled} rows across {len(violations)} tables."
                )
            if deleted:
                log.info(
                    f"Deleted {deleted} rows with non-nullable broken foreign keys."
                )
            if not nulled and not deleted:
                log.success("Database passed foreign key check.")
                return

            _mark_comics_for_update(fix_comic_pks, log)

    except Exception:
        log.exception("Integrity: foreign_key_check")

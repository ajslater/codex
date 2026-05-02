"""Database integrity checks and remedies."""

# Uses app.get_model() because functions may also be called before the models are ready on startup.
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from django.apps import apps
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from django.db.models.functions import Now

if TYPE_CHECKING:
    from django.db.models.manager import BaseManager

    from codex.models.comic import Comic

# Comic file extensions we'll consider — phantom directory-as-comic
# rows (older bug) are out of scope for parent-folder drift repair.
_COMIC_SUFFIXES = (".cbz", ".cbr", ".cb7", ".cbt", ".pdf")

# SQLite's parameter cap is 32766; leave headroom for the rare case
# where Django / the driver sneaks in extra bound values. Each rowid
# in a batched ``WHERE rowid IN (?, ?, ...)`` consumes one parameter.
_SQLITE_MAX_VARS = 32000


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


def _group_rowids_by_fix_shape(
    rows: dict[int, list[tuple[str, bool]]],
) -> dict[tuple[tuple[str, ...], bool], list[int]]:
    """
    Bunch rowids that share an UPDATE/DELETE shape into one batch.

    Two rows in the same table can have different violating columns
    (rowid 100 broken on ``publisher_id``, rowid 101 broken on
    ``imprint_id``). Grouping by ``(sorted_col_tuple, all_nullable)``
    yields the unique SQL templates we need; one ``WHERE rowid IN (...)``
    per group covers every row sharing that template.
    """
    groups: dict[tuple[tuple[str, ...], bool], list[int]] = defaultdict(list)
    for rowid, fk_cols in rows.items():
        cols = tuple(sorted(col for col, _ in fk_cols))
        all_nullable = all(nullable for _, nullable in fk_cols)
        groups[(cols, all_nullable)].append(rowid)
    return groups


def _execute_fix_batch(
    cursor,
    table_name: str,
    cols: tuple[str, ...],
    rowids: list[int],
    *,
    all_nullable: bool,
) -> int:
    """Run one batched UPDATE or DELETE; return rows affected."""
    affected = 0
    for start in range(0, len(rowids), _SQLITE_MAX_VARS):
        batch = rowids[start : start + _SQLITE_MAX_VARS]
        placeholders = ",".join(["%s"] * len(batch))
        if all_nullable:
            set_clauses = ", ".join(f'"{col}" = NULL' for col in cols)
            sql = f'UPDATE "{table_name}" SET {set_clauses} WHERE rowid IN ({placeholders})'  # noqa: S608
        else:
            sql = f'DELETE FROM "{table_name}" WHERE rowid IN ({placeholders})'  # noqa: S608
        cursor.execute(sql, batch)
        affected += cursor.rowcount
    return affected


def _fix_fk_violations(
    cursor, violations: dict[str, dict[int, list[tuple[str, bool]]]]
) -> tuple[int, int, set[int]]:
    """
    Null or delete rows with broken foreign keys.

    For each violation:
    - If all bad FK columns on the row are nullable: NULL them.
    - Otherwise: DELETE the row.

    Bunches rowids by ``(table, fk_col_set, all_nullable)`` so each
    unique fix shape becomes one ``WHERE rowid IN (...)`` query
    (chunked to stay under SQLite's 32766-variable cap) instead of
    one round-trip per violating row. ``PRAGMA foreign_key_check``
    on a corrupted DB can return thousands of rows; round-trip
    overhead dominated.

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

        for (cols, all_nullable), rowids in _group_rowids_by_fix_shape(rows).items():
            affected = _execute_fix_batch(
                cursor, table_name, cols, rowids, all_nullable=all_nullable
            )
            if all_nullable:
                nulled += affected
            else:
                deleted += affected

    return nulled, deleted, fix_comic_pks


def fix_parent_folder_drift(log, apps_registry=None) -> int:
    """
    Re-point ``Comic.parent_folder_id`` rows whose FK disagrees with the path.

    A normally-functioning importer keeps ``Comic.path`` and
    ``Comic.parent_folder.path`` consistent —
    ``Path(comic.path).parent`` always equals
    ``comic.parent_folder.path``. A past importer bug (most likely a
    botched directory-rename move during a single import event) has
    been observed to produce rare drift where the FK points at a real
    ``Folder`` row whose path no longer matches the comic's actual
    location on disk. This function detects such rows and re-points
    them at the correct ``Folder``, or surfaces a warning if no such
    folder exists in the library yet.

    Returns the number of comics whose FK was corrected. Safe to
    re-run; a no-op once the database is consistent.

    ``apps_registry`` is an optional override for the Django apps
    registry. Pass the migration-time ``apps`` argument when calling
    from a ``RunPython`` step so the function uses schema state at
    migration time rather than the live model classes. Defaults to
    the live registry.
    """
    registry = apps_registry if apps_registry is not None else apps
    comic_model = registry.get_model("codex", "Comic")
    folder_model = registry.get_model("codex", "Folder")

    folder_pk_by_key: dict[tuple[int, str], int] = {
        (lib_id, path): pk
        for pk, lib_id, path in folder_model.objects.values_list(
            "id", "library_id", "path"
        )
    }
    folder_path_by_pk: dict[int, str] = {
        pk: path for (_, path), pk in folder_pk_by_key.items()
    }

    repointed: list[tuple[int, int]] = []
    orphaned: list[tuple[int, str, str]] = []
    # ``values_list`` avoids attribute access on a generic
    # ``Model`` (which the migration-time apps registry returns)
    # — keeps the type checker happy without per-line ignores.
    for comic_id, comic_path, parent_folder_id, library_id in (
        comic_model.objects.values_list(
            "id", "path", "parent_folder_id", "library_id"
        ).iterator(chunk_size=2000)
    ):
        if not comic_path.endswith(_COMIC_SUFFIXES):
            # Phantom comic-as-folder rows are handled elsewhere.
            continue
        expected = str(Path(comic_path).parent)
        actual = folder_path_by_pk.get(parent_folder_id) if parent_folder_id else None
        if actual == expected:
            continue
        new_pk = folder_pk_by_key.get((library_id, expected))
        if new_pk is None:
            orphaned.append((comic_id, comic_path, expected))
            continue
        repointed.append((comic_id, new_pk))

    if repointed:
        with transaction.atomic():
            for comic_id, new_pk in repointed:
                comic_model.objects.filter(id=comic_id).update(parent_folder_id=new_pk)
        log.info(
            f"Re-pointed parent_folder_id for {len(repointed)} drifted comics."
        )
    else:
        log.debug("No parent_folder_id drift detected.")

    if orphaned:
        log.warning(
            f"{len(orphaned)} comics have no matching parent Folder in their library; the next import will recreate the hierarchy. First 5:"
        )
        for comic_id, comic_path, expected in orphaned[:5]:
            log.warning(
                f"  drift orphan: comic_id={comic_id} path={comic_path} expected_parent={expected}"
            )

    return len(repointed)


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

"""
Sidecar → main DB restore.

Walks every sidecar table, resolves denormalized identifiers back to
live main-DB PKs, and writes rows via the ORM. Rows whose targets
can't be found (comic deleted, tag renamed) are logged and skipped
rather than aborted.

The path is idempotent: every write goes through ``update_or_create``
or a dispatch helper that handles existing rows. Re-running restore on
top of an already-restored DB is safe.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from loguru import logger

from codex.collection import Collection
from codex.user_data.identifiers import (
    resolve_browse_collection_pks,
    watched_path_pks,
)
from codex.user_data.restore_api_keys import restore_api_keys
from codex.user_data.restore_filters import restore_list_kinds, restore_match_all
from codex.user_data.restore_reading_lists import restore_reading_lists
from codex.user_data.restore_shelves import (
    resolve_filter_shelves,
    restore_shelf_items,
    restore_shelves,
)
from codex.user_data.store import SidecarStore, get_store
from codex.xz import read_text_maybe_xz

if TYPE_CHECKING:
    from collections.abc import Callable

# The retired Default View flag, folded into SettingsDefaults.top_collection
# by migration 0055, and the Folder View flag its folders value depends on.
_BG_KEY: Final = "BG"
_FV_KEY: Final = "FV"
# The retired server-wide Stats API key flag. Its key was revoked, so a
# backup's copy is dropped rather than restored.
_AK_KEY: Final = "AK"
_RETIRED_ADMIN_FLAG_KEYS: Final = frozenset({_BG_KEY, _AK_KEY})
_LEGACY_FALLBACK_TOP_COLLECTION: Final = "publishers"
_LEGACY_REACHABLE_TOP_COLLECTIONS: Final = frozenset(
    {"publishers", "series", "comics", "arcs"}
)


@dataclass
class RestoreReport:
    """Counts of restored / updated / unmatched rows per table."""

    written: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)
    unmatched_log: list[str] = field(default_factory=list)

    def note_written(self, table: str) -> None:
        """Bump the written counter for ``table``."""
        self.written[table] = self.written.get(table, 0) + 1

    def note_skipped(self, table: str, reason: str) -> None:
        """Bump the skipped counter and append the reason."""
        self.skipped[table] = self.skipped.get(table, 0) + 1
        self.unmatched_log.append(f"[{table}] {reason}")


def restore(
    *,
    sidecar_path: Path | None = None,
    dry_run: bool = False,
) -> RestoreReport:
    """
    Restore the main DB from a sidecar backup.

    ``sidecar_path`` points at a specific backup — a compressed/plain SQL dump
    (``.sql.xz`` / ``.sql``) or a binary sidecar — and accepts the same files
    the admin restore picker offers. When omitted, the newest dated backup in
    the backups dir is used (falling back to a legacy binary sidecar, then the
    process store). ``dry_run`` resolves every row without writing.
    """
    resolved, cleanup = _resolve_sidecar(sidecar_path)
    store = None
    try:
        store = SidecarStore(resolved) if resolved is not None else get_store()
        report = RestoreReport()
        _restore_groups(store, report, dry_run=dry_run)
        _restore_users(store, report, dry_run=dry_run)
        _restore_user_groups(store, report, dry_run=dry_run)
        restore_api_keys(store, report, dry_run=dry_run)
        _restore_libraries(store, report, dry_run=dry_run)
        _restore_library_groups(store, report, dry_run=dry_run)
        _restore_admin_flags(store, report, dry_run=dry_run)
        _restore_timestamps(store, report, dry_run=dry_run)
        _restore_tagging_defaults(store, report, dry_run=dry_run)
        _restore_settings_defaults(store, report, dry_run=dry_run)
        _restore_bookmarks(store, report, dry_run=dry_run)
        # Before the shelf items and saved filters, which find lists by UUID.
        restore_reading_lists(
            store, report, resolve_browse_collection_pks, dry_run=dry_run
        )
        restore_shelves(store, report, dry_run=dry_run)
        restore_shelf_items(
            store, report, resolve_browse_collection_pks, dry_run=dry_run
        )
        _restore_settings_browser(store, report, dry_run=dry_run)
        total_written = sum(report.written.values())
        total_skipped = sum(report.skipped.values())
        mode = "Dry-run restore" if dry_run else "Restored user data"
        logger.info(f"{mode}: {total_written} written, {total_skipped} skipped.")
        return report
    finally:
        if store is not None:
            # The restore runs on an ASGI request's worker thread, which
            # is retired when the request ends. ``SidecarStore`` caches
            # its sqlite connection in a ``threading.local``, so leaving
            # it open orphans it exactly the way an unclosed Django
            # connection would (and no ASGI wrapper can reach a
            # non-Django handle).
            store.close()
        cleanup()


def _resolve_sidecar(
    sidecar_path: Path | None,
) -> tuple[Path | None, Callable[[], None]]:
    """
    Resolve the backup to read into a readable SQLite path + a cleanup callable.

    ``None`` (with a no-op cleanup) means "use the process store" — the
    file-backed default that keeps test stores and a legacy binary sidecar
    working.
    """
    if sidecar_path is not None:
        return _materialize(sidecar_path)
    from codex.settings import BACKUP_DB_DIR, CONFIG_PATH
    from codex.user_data.backups import newest_sidecar_backup

    newest = newest_sidecar_backup(BACKUP_DB_DIR, CONFIG_PATH)
    if newest is not None:
        return _materialize(newest)
    return None, lambda: None


def _materialize(path: Path) -> tuple[Path, Callable[[], None]]:
    """
    Return a path to a readable SQLite copy of a backup, cleaned up after.

    A ``.sql.xz`` / ``.sql`` dump is replayed into a temp SQLite DB, and a
    binary sidecar is copied into one. Opening the store adds the columns a
    later release introduced, so the backup itself must stay as written: the
    next restore reads from it what it really carried.
    """
    tmpdir = tempfile.TemporaryDirectory(prefix="codex-restore-")
    db_path = Path(tmpdir.name) / "sidecar.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        if path.name.endswith((".sql.xz", ".sql")):
            conn.executescript(read_text_maybe_xz(path))
        else:
            source = sqlite3.connect(path)
            try:
                source.backup(conn)
            finally:
                source.close()
    finally:
        conn.close()
    return db_path, tmpdir.cleanup


# ── Per-table restorers ──────────────────────────────────────────────


def _restore_groups(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Restore Group rows and their permissions list."""
    from django.contrib.auth.models import Group, Permission

    for row in store.fetchall("groups"):
        name = row["name"]
        if dry_run:
            report.note_written("groups")
            continue
        group, _ = Group.objects.get_or_create(name=name)
        # Resolve permission "app_label.codename" pairs to Permission rows.
        wanted: list[Permission] = []
        for perm_str in json.loads(row["permissions"] or "[]"):
            try:
                app_label, codename = perm_str.split(".", 1)
            except ValueError:
                report.note_skipped("groups", f"malformed permission {perm_str!r}")
                continue
            perm = (
                Permission.objects.filter(
                    content_type__app_label=app_label, codename=codename
                )
                .select_related("content_type")
                .first()
            )
            if perm is None:
                report.note_skipped(
                    "groups", f"missing permission {perm_str!r} for group {name!r}"
                )
                continue
            wanted.append(perm)
        group.permissions.set(wanted)
        # The exclude flag lives on the GroupAuth one-to-one.
        from codex.models.auth import GroupAuth

        GroupAuth.objects.update_or_create(
            group=group, defaults={"exclude": bool(row["exclude"])}
        )
        report.note_written("groups")


def _build_user_defaults(row) -> dict[str, Any]:
    """Map a sidecar users row to ``update_or_create`` defaults."""
    return {
        "password": row["password"] or "",
        "email": row["email"] or "",
        "first_name": row["first_name"] or "",
        "last_name": row["last_name"] or "",
        "is_staff": bool(row["is_staff"]),
        "is_superuser": bool(row["is_superuser"]),
        "is_active": bool(row["is_active"]),
        "date_joined": row["date_joined"] or None,
        "last_login": row["last_login"] or None,
    }


def _restore_users(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Restore User rows (and UserAuth.age_rating_metron)."""
    from django.contrib.auth import get_user_model

    from codex.models.age_rating import AgeRatingMetron
    from codex.models.auth import UserAuth

    user_model = get_user_model()
    for row in store.fetchall("users"):
        username = row["username"]
        if dry_run:
            report.note_written("users")
            continue
        user, _ = user_model.objects.update_or_create(
            username=username,
            defaults=_build_user_defaults(row),
        )
        # AgeRatingMetron name → row.
        age_rating = None
        name = row["age_rating_metron_name"]
        if name:
            age_rating = AgeRatingMetron.objects.filter(name=name).first()
            if age_rating is None:
                report.note_skipped(
                    "users",
                    f"age rating {name!r} not in main DB for user {username!r}",
                )
        UserAuth.objects.update_or_create(
            user=user, defaults={"age_rating_metron": age_rating}
        )
        report.note_written("users")


def _restore_user_groups(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Restore the User.groups M2M."""
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    user_model = get_user_model()
    for row in store.fetchall("user_groups"):
        if dry_run:
            report.note_written("user_groups")
            continue
        user = user_model.objects.filter(username=row["username"]).first()
        if user is None:
            report.note_skipped("user_groups", f"missing user {row['username']!r}")
            continue
        group = Group.objects.filter(name=row["group_name"]).first()
        if group is None:
            report.note_skipped("user_groups", f"missing group {row['group_name']!r}")
            continue
        user.groups.add(group)
        report.note_written("user_groups")


def _restore_libraries(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Restore Library rows."""
    import datetime as dt

    from codex.models.library import Library

    for row in store.fetchall("libraries"):
        if dry_run:
            report.note_written("libraries")
            continue
        defaults: dict[str, Any] = {
            "events": bool(row["events"]),
            "poll": bool(row["poll"]),
            "last_poll": row["last_poll"] or None,
        }
        if row["poll_every"]:
            # Stored as total-seconds float by ``serialize_library``.
            defaults["poll_every"] = dt.timedelta(seconds=float(row["poll_every"]))
        Library.objects.update_or_create(path=row["path"], defaults=defaults)
        report.note_written("libraries")


def _restore_library_groups(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Restore Library.groups M2M."""
    from django.contrib.auth.models import Group

    from codex.models.library import Library

    for row in store.fetchall("library_groups"):
        if dry_run:
            report.note_written("library_groups")
            continue
        library = Library.objects.filter(path=row["library_path"]).first()
        if library is None:
            report.note_skipped(
                "library_groups", f"missing library {row['library_path']!r}"
            )
            continue
        group = Group.objects.filter(name=row["group_name"]).first()
        if group is None:
            report.note_skipped(
                "library_groups", f"missing group {row['group_name']!r}"
            )
            continue
        library.groups.add(group)
        report.note_written("library_groups")


def _restore_admin_flags(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Restore AdminFlag rows."""
    from codex.models.admin import AdminFlag
    from codex.models.age_rating import AgeRatingMetron

    for row in store.fetchall("admin_flags"):
        if row["key"] in _RETIRED_ADMIN_FLAG_KEYS:
            # Default View moved to SettingsDefaults.top_collection; the
            # settings_defaults restore maps a legacy BG row onto it. The
            # server-wide Stats API key was revoked.
            continue
        if dry_run:
            report.note_written("admin_flags")
            continue
        age_rating = None
        name = row["age_rating_metron_name"]
        if name:
            age_rating = AgeRatingMetron.objects.filter(name=name).first()
            if age_rating is None:
                report.note_skipped(
                    "admin_flags",
                    f"age rating {name!r} not in main DB for flag {row['key']!r}",
                )
        AdminFlag.objects.update_or_create(
            key=row["key"],
            defaults={
                "on": bool(row["on_flag"]),
                "value": row["value"] or "",
                "age_rating_metron": age_rating,
            },
        )
        report.note_written("admin_flags")


def _restore_timestamps(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Restore Timestamp rows."""
    from codex.models.admin import Timestamp

    for row in store.fetchall("timestamps"):
        if dry_run:
            report.note_written("timestamps")
            continue
        # Skip the legacy ``AP`` row — the API key moved to AdminFlag,
        # so importing it here would create an orphan Timestamp row
        # rejected by the post-0051 choices field. Backups carrying
        # the row are silently dropped; the key it held has been revoked.
        if row["key"] == "AP":
            continue
        # Older sidecars used a ``version`` column; current ones use
        # ``value``. ``sqlite3.Row`` has no ``.get`` — peek at the
        # row's column names to pick the right key.
        cols = set(row.keys())
        if "value" in cols:
            value = row["value"] or ""
        elif "version" in cols:
            value = row["version"] or ""
        else:
            value = ""
        Timestamp.objects.update_or_create(key=row["key"], defaults={"value": value})
        report.note_written("timestamps")


# Tagging default columns, by how a value is read. Any one a backup did not
# carry leaves the stored setting alone: a backup older than a setting has
# nothing to say about it.
_TAGGING_TEXT: Final = MappingProxyType(
    {
        "default_match_mode": "auto",
        "default_prompts_mode": "ask",
        "default_effort": "",
        "metron_key": "",
        "comicvine_key": "",
        "comicvine_url": "",
        "versedb_key": "",
    }
)
_TAGGING_JSON: Final = ("default_formats", "default_sources")
_TAGGING_FLAGS: Final = ("delete_original", "merge_all_sources", "rename_files")


def _build_tagging_defaults(row, carried: frozenset[str]) -> dict[str, Any]:
    """
    Map a sidecar tagging_defaults row to ``update_or_create`` defaults.

    ``carried`` is what the backup itself had: the sidecar store adds a
    newer column to an older file with its default, so a column the row
    shows is not proof the backup set it. Columns this release dropped,
    such as ``metron_url`` or ``active_session_id``, are not read at all.
    """
    defaults: dict[str, Any] = {
        key: row[key] or fallback
        for key, fallback in _TAGGING_TEXT.items()
        if key in carried
    }
    defaults.update(
        {key: json.loads(row[key] or "[]") for key in _TAGGING_JSON if key in carried}
    )
    defaults.update({key: bool(row[key]) for key in _TAGGING_FLAGS if key in carried})
    return defaults


def _restore_tagging_defaults(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Restore the ComicboxTaggingDefaults singleton."""
    from codex.models.admin import ComicboxTaggingDefaults

    rows = store.fetchall("tagging_defaults")
    if not rows:
        return
    row = rows[0]
    if dry_run:
        report.note_written("tagging_defaults")
        return
    carried = store.carried_columns("tagging_defaults")
    ComicboxTaggingDefaults.objects.update_or_create(
        pk=1, defaults=_build_tagging_defaults(row, carried)
    )
    report.note_written("tagging_defaults")


def _build_settings_defaults(row, carried: frozenset[str]) -> dict[str, Any]:
    """
    Map a sidecar settings_defaults row to ``update_or_create`` defaults.

    ``carried`` is what the backup itself had; see the tagging defaults.
    """
    from codex.choices.browser import clean_table_columns
    from codex.user_data.serializers import (
        SETTINGS_DEFAULTS_BOOLS,
        SETTINGS_DEFAULTS_TEXT,
    )

    defaults: dict[str, Any] = {
        key: row[key]
        for key in SETTINGS_DEFAULTS_TEXT
        if key in carried and row[key] is not None
    }
    defaults.update(
        {key: bool(row[key]) for key in SETTINGS_DEFAULTS_BOOLS if key in carried}
    )
    # Retired sort keys and columns are renamed, as the per-user rows are.
    if "order_by" in defaults:
        defaults["order_by"] = _rename_sort_key(defaults["order_by"])
    if "table_columns" in carried:
        table_columns = _rename_table_columns(row["table_columns"])
        defaults["table_columns"], _ = clean_table_columns(table_columns)
    return defaults


def legacy_top_collection(*, bg_on: bool, bg_value: str, folder_view_on: bool) -> str:
    """
    Map a retired Default View (BG) flag onto the effective top collection.

    Mirrors migration 0055: the stored value is the one new sessions
    actually landed on. Imprints and volumes are hidden by the factory show
    flags and folders needs Folder View, so those fall back to publishers.
    """
    if not bg_on:
        return _LEGACY_FALLBACK_TOP_COLLECTION
    if bg_value in _LEGACY_REACHABLE_TOP_COLLECTIONS:
        return bg_value
    if bg_value == "folders" and folder_view_on:
        return bg_value
    return _LEGACY_FALLBACK_TOP_COLLECTION


def _legacy_settings_defaults(store: SidecarStore) -> dict[str, Any] | None:
    """Map a pre-SettingsDefaults backup's BG flag onto ``top_collection``."""
    flags = {
        row["key"]: row
        for row in store.fetchall("admin_flags")
        if row["key"] in (_BG_KEY, _FV_KEY)
    }
    bg = flags.get(_BG_KEY)
    if bg is None:
        return None
    fv = flags.get(_FV_KEY)
    top_collection = legacy_top_collection(
        bg_on=bool(bg["on_flag"]),
        bg_value=bg["value"] or "",
        folder_view_on=bool(fv and fv["on_flag"]),
    )
    return {"top_collection": top_collection}


def _restore_settings_defaults(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """
    Restore the SettingsDefaults singleton.

    A backup taken before the singleton existed still gets an empty
    ``settings_defaults`` table (the sidecar schema is applied on every
    connection), so "no row" is the legacy test: its BG flag maps onto
    ``top_collection`` instead.
    """
    from codex.models.admin import SettingsDefaults

    rows = store.fetchall("settings_defaults")
    defaults = (
        _build_settings_defaults(rows[0], store.carried_columns("settings_defaults"))
        if rows
        else _legacy_settings_defaults(store)
    )
    if defaults is None:
        return
    if not dry_run:
        SettingsDefaults.objects.update_or_create(pk=1, defaults=defaults)
    report.note_written("settings_defaults")


def _restore_bookmarks(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Restore Bookmark rows; missing comics are logged and skipped."""
    from django.contrib.auth import get_user_model

    from codex.models import Comic
    from codex.models.bookmark import Bookmark

    user_model = get_user_model()
    for row in store.fetchall("bookmarks"):
        if dry_run:
            report.note_written("bookmarks")
            continue
        user = user_model.objects.filter(username=row["username"]).first()
        if user is None:
            report.note_skipped("bookmarks", f"missing user {row['username']!r}")
            continue
        comic_pks = watched_path_pks(Comic, row["comic_path"])
        if not comic_pks:
            report.note_skipped("bookmarks", f"missing comic {row['comic_path']!r}")
            continue
        for comic_pk in comic_pks:
            Bookmark.objects.update_or_create(
                user=user,
                session=None,
                comic_id=comic_pk,
                defaults={"page": row["page"], "finished": bool(row["finished"])},
            )
        report.note_written("bookmarks")


# ── Browser settings ─────────────────────────────────────────────────


def _restore_settings_browser(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """
    Restore SettingsBrowser + its 1:1 filters + last_route.

    The three sidecar tables share the ``(username, client, name)`` key,
    so we walk them together.
    """
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    filters_by_key = {
        (r["username"], r["client"], r["name"]): r
        for r in store.fetchall("settings_filters")
    }
    last_route_by_key = {
        (r["username"], r["client"], r["name"]): r
        for r in store.fetchall("settings_last_route")
    }

    for row in store.fetchall("settings_browser"):
        _restore_one_settings_browser(
            row,
            user_model,
            filters_by_key,
            last_route_by_key,
            report,
            dry_run=dry_run,
        )


# Filter/sort keys renamed across codex versions; sidecar backups from
# older versions still carry the old name (0048: critical -> community).
# This map also resolves *filter* columns by their legacy name, so only
# renames that applied to a filter column belong here.
_LEGACY_KEY_RENAMES: Final[dict[str, str]] = {"critical_rating": "community_rating"}

# Sort keys retired into another key. Sort-only, because there was never
# an ``alternate_number`` filter column for ``_resolve_filter_column``
# to look for (the Alternate Number sort merged into Reprints before
# either shipped).
#
# No migration pairs with this: the retired key never reached a release,
# so only a sidecar written by a development build can still carry it —
# and a sidecar outlives the database it came from.
_SORT_KEY_RENAMES: Final[dict[str, str]] = {
    **_LEGACY_KEY_RENAMES,
    "alternate_number": "reprints",
    # Favorites became shelves and shelves became reading lists: both the
    # old flags' sort and column are now the Reading Lists column.
    "favorite": "reading_lists",
    "shelved": "reading_lists",
    # Story arcs and reading lists are one concept: Reading Lists.
    "story_arcs": "reading_lists",
}


def _resolve_filter_column(row_keys, column: str) -> str | None:
    """Sidecar column holding ``column``'s value: itself, its legacy name, or None."""
    if column in row_keys:
        return column
    legacy = next(
        (old for old, new in _LEGACY_KEY_RENAMES.items() if new == column), None
    )
    if legacy and legacy in row_keys:
        return legacy
    return None


def _row_column(row, column: str):
    """Read a column a sidecar written by an older codex may not carry."""
    try:
        return row[column]
    except (IndexError, KeyError):
        # sqlite3.Row raises IndexError, a plain mapping raises KeyError.
        return None


def _rename_sort_key(key) -> str:
    """Rename one retired sort key. Sidecar JSON can hold anything."""
    key = key if isinstance(key, str) else ""
    return _SORT_KEY_RENAMES.get(key, key)


def _rename_extra_keys(entries) -> list:
    """Rename retired sort keys in an extras list, dropping duplicates."""
    if not isinstance(entries, list):
        return []
    renamed: list = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = _rename_sort_key(entry.get("key"))
        if key in seen:
            # Both a retired key and its replacement were stored; one
            # column can only carry one sort, so the first one wins.
            continue
        seen.add(key)
        renamed.append({**entry, "key": key})
    return renamed


def _rename_memory_keys(memory) -> dict:
    """Rename retired sort keys inside a collection_order_memory map."""
    if not isinstance(memory, dict):
        return {}
    for remembered in memory.values():
        if not isinstance(remembered, dict):
            continue
        remembered["order_by"] = _rename_sort_key(remembered.get("order_by"))
        remembered["order_extra_keys"] = _rename_extra_keys(
            remembered.get("order_extra_keys")
        )
    return memory


def _rename_table_columns(raw) -> dict:
    """Rename retired column keys in a table_columns JSON blob."""
    table_columns = json.loads(raw or "{}")
    if not isinstance(table_columns, dict):
        return {}
    # Oldest shape: a flat ``{column: bool}`` map.
    for old, new in _SORT_KEY_RENAMES.items():
        if old in table_columns:
            table_columns[new] = table_columns.pop(old)
    # Current shape: ``{top_collection: [column, ...]}``.
    for top_collection, columns in table_columns.items():
        if not isinstance(columns, list):
            continue
        renamed: list = []
        for column in columns:
            key = _SORT_KEY_RENAMES.get(column, column)
            if key not in renamed:
                renamed.append(key)
        table_columns[top_collection] = renamed
    return table_columns


_BROWSER_STR_COLUMNS: Final[tuple[str, ...]] = (
    "top_collection",
    "search",
    "view_mode",
    "table_cover_size",
)
_BROWSER_BOOL_COLUMNS: Final[tuple[str, ...]] = (
    "order_reverse",
    "twenty_four_hour_time",
    "always_show_filename",
)


def _build_browser_defaults(row, show) -> dict[str, Any]:
    """Map a sidecar settings_browser row to ``update_or_create`` defaults."""
    defaults: dict[str, Any] = {
        "show": show,
        "order_by": _rename_sort_key(row["order_by"]),
        "order_extra_keys": _rename_extra_keys(
            json.loads(row["order_extra_keys"] or "[]")
        ),
        "collection_order_memory": _rename_memory_keys(
            json.loads(_row_column(row, "collection_order_memory") or "{}")
        ),
        "table_columns": _rename_table_columns(row["table_columns"]),
    }
    defaults.update({column: row[column] or "" for column in _BROWSER_STR_COLUMNS})
    defaults.update({column: bool(row[column]) for column in _BROWSER_BOOL_COLUMNS})
    # Newer than some backups; on unless the backup says otherwise.
    show_missing = _row_column(row, "show_missing_issues")
    defaults["show_missing_issues"] = show_missing is None or bool(show_missing)
    return defaults


def _restore_one_settings_browser(
    row,
    user_model,
    filters_by_key: dict,
    last_route_by_key: dict,
    report: RestoreReport,
    *,
    dry_run: bool,
) -> None:
    """Restore one settings_browser row + cascade into filters / last_route."""
    from codex.models.settings import SettingsBrowser, SettingsBrowserShow

    if dry_run:
        report.note_written("settings_browser")
        return
    user = user_model.objects.filter(username=row["username"]).first()
    if user is None:
        report.note_skipped("settings_browser", f"missing user {row['username']!r}")
        return
    show, _ = SettingsBrowserShow.objects.get_or_create(
        publishers=bool(row["show_p"]),
        imprints=bool(row["show_i"]),
        series=bool(row["show_s"]),
        volumes=bool(row["show_v"]),
    )
    browser, _ = SettingsBrowser.objects.update_or_create(
        user=user,
        client=row["client"],
        name=row["name"],
        defaults=_build_browser_defaults(row, show),
    )
    report.note_written("settings_browser")

    key = (row["username"], row["client"], row["name"])
    if key in filters_by_key:
        _restore_one_filter(filters_by_key[key], browser, report)
    if key in last_route_by_key:
        _restore_one_last_route(last_route_by_key[key], browser, report)


def _resolve_filter_tags(column: str, raw: list, browser, report: RestoreReport):
    """Resolve a tag-name list back to PKs, reporting unmatched names."""
    from codex.user_data.identifiers import (
        tag_model_for_filter,
        tag_name_field_for_filter,
    )

    model = tag_model_for_filter(column)
    if model is None:
        return []
    name_field = tag_name_field_for_filter(column)
    pks = list(
        model.objects.filter(**{f"{name_field}__in": raw}).values_list("pk", flat=True)
    )
    # A non-unique name field (``Reprint.series_name``) can resolve to
    # more rows than the dump held; only a shortfall is a real drop.
    if len(pks) < len(raw):
        dropped = len(raw) - len(pks)
        report.note_skipped(
            "settings_filters",
            f"dropped {dropped} {column} tag(s) unmatched for {browser.user.username}",
        )
    return pks


def _story_arc_list_pks(row_keys, row) -> list[int]:
    """
    Resolve an old backup's story-arc filter to the global lists of its names.

    Story arcs and reading lists are one concept now, so a filter on an arc
    is a filter on the arc's list. Of several global lists of one name the
    first made is the one the tags built.
    """
    from codex.models.readinglist import ReadingList

    if "story_arcs" not in row_keys:
        return []
    names = json.loads(row["story_arcs"] or "[]")
    first: dict[str, int] = {}
    rows = (
        ReadingList.objects.filter(user__isnull=True, name__in=names)
        .order_by("pk")
        .values_list("name", "pk")
    )
    for name, pk in rows:
        first.setdefault(name, pk)
    return [first[name] for name in names if name in first]


def _tag_list_pks(row_keys, row, browser) -> list[int]:
    """
    Resolve the filter's tags refs to the lists now holding those tags.

    A list from tags alone is not backed up, so after a rebuild the tag
    sync made it again under a new uuid; its tags source still has the ref.
    """
    from codex.models.readinglist import ReadingListSource, ReadingListSourceKind
    from codex.views.auth import GroupACLMixin

    if "reading_list_tags" not in row_keys or not (
        refs := json.loads(row["reading_list_tags"] or "[]")
    ):
        return []
    visible = GroupACLMixin.reading_list_visibility_filter(
        browser.user, "reading_list__"
    )
    return list(
        ReadingListSource.objects.filter(
            visible, kind=ReadingListSourceKind.TAGS, ref__in=refs
        )
        .order_by("reading_list_id")
        .values_list("reading_list_id", flat=True)
    )


def _resolve_filter_reading_lists(row_keys, row, browser) -> list[int]:
    """Resolve reading list uuids to the pks of lists the owner may see."""
    from codex.models.readinglist import ReadingList
    from codex.views.auth import GroupACLMixin

    pks: list[int] = []
    if "reading_lists" in row_keys and (
        uuids := json.loads(row["reading_lists"] or "[]")
    ):
        visible = GroupACLMixin.reading_list_visibility_filter(browser.user)
        pks = list(
            ReadingList.objects.filter(visible, uuid__in=uuids)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
    return list(
        dict.fromkeys(
            [
                *pks,
                *_tag_list_pks(row_keys, row, browser),
                *_story_arc_list_pks(row_keys, row),
            ]
        )
    )


def _restore_one_filter(row, browser, report: RestoreReport) -> None:
    """Resolve tag-name lists in the sidecar back to PK lists."""
    from codex.models.settings import SettingsBrowserFilters
    from codex.user_data.identifiers import FILTER_TAG_COLUMNS

    row_keys = row.keys()
    defaults: dict[str, Any] = {
        "bookmark": row["bookmark"] or "",
        "reading_list_kind": restore_list_kinds(row_keys, row),
        "match_all": restore_match_all(row_keys, row),
        # An older backup's shelves are personal lists now: one filter.
        "reading_lists": list(
            dict.fromkeys(
                [
                    *_resolve_filter_reading_lists(row_keys, row, browser),
                    *resolve_filter_shelves(row, row_keys, browser),
                ]
            )
        ),
    }
    for column in SettingsBrowserFilters.FILTER_KEYS:
        if column in defaults:
            continue
        read_column = _resolve_filter_column(row_keys, column)
        if read_column is None:
            defaults[column] = []
            continue
        raw = json.loads(row[read_column] or "[]")
        defaults[column] = (
            _resolve_filter_tags(column, raw, browser, report)
            if column in FILTER_TAG_COLUMNS
            else raw
        )
    SettingsBrowserFilters.objects.update_or_create(browser=browser, defaults=defaults)
    report.note_written("settings_filters")


def _resolve_last_route_pks(
    collection: str, decoded: list, report: RestoreReport
) -> list[int]:
    """Map sidecar identifier tuples to main-DB PKs; missing rows drop + log."""
    if collection == Collection.ROOT or not decoded:
        return []
    from codex.models.collection_models import BROWSE_COLLECTION_MODELS

    target_model = BROWSE_COLLECTION_MODELS.get(collection)
    if target_model is None:
        return []
    pks: list[int] = []
    for parts in decoded:
        resolved = resolve_browse_collection_pks(collection, parts, target_model)
        if not resolved:
            report.note_skipped(
                "settings_last_route",
                f"unresolvable last-route {collection!r} target {parts!r}",
            )
            continue
        # One route pk per saved identifier: overlapping libraries must not
        # widen a remembered single-collection route into a multi-pk one.
        pks.append(resolved[0])
    return pks


def _restore_one_last_route(row, browser, report: RestoreReport) -> None:
    """Restore a single ``settings_last_route`` row."""
    from codex.models.settings import SettingsBrowserLastRoute

    collection = row["collection"]
    decoded = json.loads(row["pks_json"] or "[]")
    pks = _resolve_last_route_pks(collection, decoded, report)
    SettingsBrowserLastRoute.objects.update_or_create(
        browser=browser,
        defaults={"collection": collection, "pks": pks, "page": row["page"] or 1},
    )
    report.note_written("settings_last_route")


def write_log(report: RestoreReport, path: Path) -> None:
    """Write the unmatched-rows log to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# codex restore_user_data log",
        f"written: {report.written}",
        f"skipped: {report.skipped}",
        "",
        *report.unmatched_log,
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f"Restore log written to {path}")

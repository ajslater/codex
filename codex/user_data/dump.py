"""
Snapshot every user-bound row from the main DB into the sidecar.

The sidecar is **not** continuously mirrored. A dump is taken on demand
(``POST /admin/dump-user-data``) and on a nightly schedule
(:class:`JanitorDumpUserDataTask`). Each dump replaces the sidecar's
contents wholesale — old rows that no longer exist in the main DB are
cleared first so the snapshot is a true point-in-time copy.

A dump is small and fast (single-digit seconds even on large
libraries): every tracked table is read once, serialized, and written.
Restore reads it back via :mod:`codex.user_data.restore`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from loguru import logger

from codex.user_data import serializers
from codex.user_data.store import SidecarStore, get_store

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

# Tables to truncate at the start of every dump. The schema also
# defines ``schema_version``; that one is *not* truncated — it's the
# bookkeeping row stamped by :func:`SidecarStore._ensure_schema`.
_TRACKED_TABLES: Final[tuple[str, ...]] = (
    "users",
    "groups",
    "user_groups",
    "libraries",
    "library_groups",
    "bookmarks",
    "favorites",
    "settings_browser",
    "settings_filters",
    "settings_last_route",
    "admin_flags",
    "timestamps",
    "tagging_defaults",
)


def _dump_queryset(
    store: SidecarStore, queryset: Iterable, serializer: Callable
) -> int:
    """Serialize and upsert every row; return the count of successful writes."""
    written = 0
    for instance in queryset:
        try:
            result = serializer(instance)
        except Exception:
            instance_name = type(instance).__name__
            logger.exception(
                f"Sidecar dump serialize failed for {instance_name} pk={instance.pk}"
            )
            continue
        if result is None:
            continue
        table, key_columns, data = result
        try:
            store.upsert(table, key_columns, data)
        except Exception:
            logger.exception(f"Sidecar dump upsert failed for {table!r}")
            continue
        written += 1
    return written


def _clear_sidecar(store: SidecarStore) -> None:
    """Truncate every tracked table inside a single transaction."""
    conn = store.connection()
    with conn:
        for table in _TRACKED_TABLES:
            # Table names come from a static module-level tuple, not user input.
            conn.execute(f"DELETE FROM {table}")  # noqa: S608


def dump_user_data(store: SidecarStore | None = None) -> dict[str, int]:
    """
    Replace the sidecar with a fresh snapshot of every tracked main-DB row.

    Writes into ``store`` (default: the process-wide file-backed sidecar). The
    production path passes an in-memory store and serializes the result to a
    compressed dump — see :func:`snapshot_sidecar`. Returns a dict of
    table → row-count for logging / API response.
    """
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    from codex.models.admin import (
        AdminFlag,
        ComicboxTaggingDefaults,
        Timestamp,
    )
    from codex.models.bookmark import Bookmark
    from codex.models.favorite import Favorite
    from codex.models.library import Library
    from codex.models.settings import (
        SettingsBrowser,
        SettingsBrowserFilters,
        SettingsBrowserLastRoute,
    )

    if store is None:
        store = get_store()
    _clear_sidecar(store)

    user_model = get_user_model()
    counts: dict[str, int] = {}

    counts["groups"] = _dump_queryset(
        store,
        Group.objects.prefetch_related("permissions__content_type"),
        serializers.serialize_group,
    )
    counts["users"] = _dump_queryset(
        store,
        user_model.objects.select_related("userauth__age_rating_metron"),
        serializers.serialize_user,
    )
    counts["user_groups"] = _dump_user_groups(store)
    counts["libraries"] = _dump_queryset(
        store, Library.objects.all(), serializers.serialize_library
    )
    counts["library_groups"] = _dump_library_groups(store)
    counts["admin_flags"] = _dump_queryset(
        store,
        AdminFlag.objects.select_related("age_rating_metron"),
        serializers.serialize_admin_flag,
    )
    counts["timestamps"] = _dump_queryset(
        store, Timestamp.objects.all(), serializers.serialize_timestamp
    )
    counts["tagging_defaults"] = _dump_queryset(
        store,
        ComicboxTaggingDefaults.objects.all(),
        serializers.serialize_tagging_defaults,
    )
    counts["bookmarks"] = _dump_queryset(
        store,
        Bookmark.objects.filter(user__isnull=False).select_related("user", "comic"),
        serializers.serialize_bookmark,
    )
    counts["favorites"] = _dump_queryset(
        store,
        Favorite.objects.select_related("user"),
        serializers.serialize_favorite,
    )
    counts["settings_browser"] = _dump_queryset(
        store,
        SettingsBrowser.objects.filter(user__isnull=False).select_related(
            "user", "show"
        ),
        serializers.serialize_settings_browser,
    )
    counts["settings_filters"] = _dump_queryset(
        store,
        SettingsBrowserFilters.objects.select_related("browser__user"),
        serializers.serialize_settings_filters,
    )
    counts["settings_last_route"] = _dump_queryset(
        store,
        SettingsBrowserLastRoute.objects.select_related("browser__user"),
        serializers.serialize_settings_last_route,
    )

    return counts


def snapshot_sidecar() -> dict[str, int]:
    """
    Write a dated, xz-compressed SQL snapshot of all user data into the backups dir.

    Populates an in-memory sidecar, streams ``Connection.iterdump()`` straight
    into an ``lzma`` text file (a single write — no uncompressed intermediate),
    prunes the dated set to the retention cap, and removes any legacy
    uncompressed sidecar. This is the production entry point (nightly janitor +
    admin "Snapshot Now"); :func:`dump_user_data` stays store-agnostic for tests.
    """
    import lzma

    from codex.settings import BACKUP_DB_DIR, CONFIG_PATH
    from codex.user_data.backups import SIDECAR_BACKUP_PATTERN, sidecar_backup_path
    from codex.xz import prune_dated, xz_preset

    preset = xz_preset()
    mem = SidecarStore.in_memory()
    try:
        counts = dump_user_data(store=mem)
        dest = sidecar_backup_path(BACKUP_DB_DIR)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".tmp")
        try:
            with lzma.open(tmp, "wt", encoding="utf-8", preset=preset) as out:
                for line in mem.connection().iterdump():
                    out.write(line + "\n")
            tmp.replace(dest)
        finally:
            tmp.unlink(missing_ok=True)
    finally:
        mem.close()

    prune_dated(BACKUP_DB_DIR, SIDECAR_BACKUP_PATTERN)
    _remove_legacy_sidecar(CONFIG_PATH)
    total = sum(counts.values())
    logger.info(f"Snapshotted user data sidecar to {dest.name}: {total} rows")
    return counts


def _remove_legacy_sidecar(config_dir: Path) -> None:
    """Drop the pre-compression binary sidecar; the dated snapshot supersedes it."""
    legacy = config_dir / "user_data.sqlite"
    for suffix in ("", "-wal", "-shm"):
        legacy.with_name(legacy.name + suffix).unlink(missing_ok=True)


def _dump_user_groups(store: SidecarStore) -> int:
    """Walk User.groups M2M and write each (username, group_name) pair."""
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    written = 0
    qs = user_model.objects.prefetch_related("groups")
    for user in qs:
        for group in user.groups.all():
            try:
                store.upsert(
                    "user_groups",
                    ("username", "group_name"),
                    {"username": user.username, "group_name": group.name},
                )
            except Exception:
                logger.exception("Sidecar dump user_groups upsert failed")
                continue
            written += 1
    return written


def _dump_library_groups(store: SidecarStore) -> int:
    """Walk Library.groups M2M and write each (library_path, group_name)."""
    from codex.models.library import Library

    written = 0
    qs = Library.objects.prefetch_related("groups")
    for library in qs:
        for group in library.groups.all():
            try:
                store.upsert(
                    "library_groups",
                    ("library_path", "group_name"),
                    {"library_path": str(library.path), "group_name": group.name},
                )
            except Exception:
                logger.exception("Sidecar dump library_groups upsert failed")
                continue
            written += 1
    return written

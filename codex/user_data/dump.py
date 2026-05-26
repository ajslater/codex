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
from codex.user_data.store import get_store

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

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


def _dump_queryset(queryset: Iterable, serializer: Callable) -> int:
    """Serialize and upsert every row; return the count of successful writes."""
    written = 0
    store = get_store()
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


def _clear_sidecar() -> None:
    """Truncate every tracked table inside a single transaction."""
    conn = get_store().connection()
    with conn:
        for table in _TRACKED_TABLES:
            # Table names come from a static module-level tuple, not user input.
            conn.execute(f"DELETE FROM {table}")  # noqa: S608


def dump_user_data() -> dict[str, int]:
    """
    Replace the sidecar with a fresh snapshot of every tracked main-DB row.

    Returns a dict of table → row-count for logging / API response.
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

    _clear_sidecar()

    user_model = get_user_model()
    counts: dict[str, int] = {}

    counts["groups"] = _dump_queryset(
        Group.objects.prefetch_related("permissions__content_type"),
        serializers.serialize_group,
    )
    counts["users"] = _dump_queryset(
        user_model.objects.select_related("userauth__age_rating_metron"),
        serializers.serialize_user,
    )
    counts["user_groups"] = _dump_user_groups()
    counts["libraries"] = _dump_queryset(
        Library.objects.all(), serializers.serialize_library
    )
    counts["library_groups"] = _dump_library_groups()
    counts["admin_flags"] = _dump_queryset(
        AdminFlag.objects.select_related("age_rating_metron"),
        serializers.serialize_admin_flag,
    )
    counts["timestamps"] = _dump_queryset(
        Timestamp.objects.all(), serializers.serialize_timestamp
    )
    counts["tagging_defaults"] = _dump_queryset(
        ComicboxTaggingDefaults.objects.all(),
        serializers.serialize_tagging_defaults,
    )
    counts["bookmarks"] = _dump_queryset(
        Bookmark.objects.filter(user__isnull=False).select_related("user", "comic"),
        serializers.serialize_bookmark,
    )
    counts["favorites"] = _dump_queryset(
        Favorite.objects.select_related("user"),
        serializers.serialize_favorite,
    )
    counts["settings_browser"] = _dump_queryset(
        SettingsBrowser.objects.filter(user__isnull=False).select_related(
            "user", "show"
        ),
        serializers.serialize_settings_browser,
    )
    counts["settings_filters"] = _dump_queryset(
        SettingsBrowserFilters.objects.select_related("browser__user"),
        serializers.serialize_settings_filters,
    )
    counts["settings_last_route"] = _dump_queryset(
        SettingsBrowserLastRoute.objects.select_related("browser__user"),
        serializers.serialize_settings_last_route,
    )

    return counts


def _dump_user_groups() -> int:
    """Walk User.groups M2M and write each (username, group_name) pair."""
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    store = get_store()
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


def _dump_library_groups() -> int:
    """Walk Library.groups M2M and write each (library_path, group_name)."""
    from codex.models.library import Library

    store = get_store()
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

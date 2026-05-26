"""
One-shot full dump of user data from the main DB into the sidecar.

Runs the first time the sidecar opens against an empty database — i.e.
either a fresh install, or an upgrade from a pre-sidecar codex against
an existing main DB. The signal-driven mirror covers steady-state
writes; backfill catches everything that was already in place.

Idempotent: every write is an upsert keyed on a stable identifier, so
re-running backfill is safe.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from codex.user_data import serializers
from codex.user_data.store import get_store

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


def _dump_queryset(
    queryset: Iterable,
    serializer: Callable,
) -> int:
    """Serialize and upsert every row; return the count of successful writes."""
    written = 0
    store = get_store()
    for instance in queryset:
        try:
            result = serializer(instance)
        except Exception:
            instance_name = type(instance).__name__
            logger.exception(
                f"Sidecar backfill serialize failed for {instance_name} pk={instance.pk}"
            )
            continue
        if result is None:
            continue
        table, key_columns, data = result
        try:
            store.upsert(table, key_columns, data)
        except Exception:
            logger.exception(f"Sidecar backfill upsert failed for {table!r}")
            continue
        written += 1
    return written


def run_backfill() -> dict[str, int]:
    """
    Mirror every tracked main-DB row into the sidecar.

    Returns a dict of table → row-count for logging.
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
    counts["user_groups"] = _backfill_user_groups()
    counts["libraries"] = _dump_queryset(
        Library.objects.all(), serializers.serialize_library
    )
    counts["library_groups"] = _backfill_library_groups()
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


def _backfill_user_groups() -> int:
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
                logger.exception("Sidecar backfill user_groups upsert failed")
                continue
            written += 1
    return written


def _backfill_library_groups() -> int:
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
                logger.exception("Sidecar backfill library_groups upsert failed")
                continue
            written += 1
    return written


def backfill_if_empty() -> dict[str, int] | None:
    """
    Run :func:`run_backfill` only when the sidecar has no data yet.

    Called once at startup. Returns the counts dict if backfill ran,
    ``None`` if the sidecar already had data (and backfill was skipped).
    """
    store = get_store()
    try:
        if not store.is_empty():
            return None
    except Exception:
        logger.exception("Sidecar is_empty check failed")
        return None
    logger.info("Sidecar empty — running first-time backfill from main DB.")
    counts = run_backfill()
    logger.info(f"Sidecar backfill complete: {counts}")
    return counts

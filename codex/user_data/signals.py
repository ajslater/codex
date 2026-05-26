"""
Sidecar mirror signal handlers.

Every tracked model gets a ``post_save`` and (where applicable)
``post_delete`` handler that serializes the row and writes through to
the sidecar. Handlers are best-effort: failures are caught and logged,
never re-raised. The signal connections are wired by
:func:`connect_user_data_signals`, called from
:func:`codex.signals.django_signals.connect_signals` after
``django.setup()``.

The sidecar store itself opens its connection lazily on first write,
so importing this module before settings/db are ready is safe.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from codex.user_data import serializers
from codex.user_data.identifiers import (
    encode_identifier,
    identifier_for_browse_group,
)
from codex.user_data.store import get_store

if TYPE_CHECKING:
    from collections.abc import Callable


def _safe_upsert(
    instance,
    serializer: Callable[[Any], tuple[str, tuple[str, ...], dict[str, Any]] | None],
) -> None:
    """Run ``serializer`` and upsert; swallow + log any failure."""
    try:
        result = serializer(instance)
    except Exception:
        logger.exception(f"Sidecar serialize failed for {type(instance).__name__}")
        return
    if result is None:
        return
    table, key_columns, data = result
    try:
        get_store().upsert(table, key_columns, data)
    except Exception:
        logger.exception(f"Sidecar upsert failed for table {table!r}")


def _safe_delete(table: str, where: dict[str, Any]) -> None:
    """Delete from the sidecar; swallow + log any failure."""
    try:
        get_store().delete(table, where)
    except Exception:
        logger.exception(f"Sidecar delete failed for table {table!r}")


# ── post_save handlers (one per tracked model) ───────────────────────


def _on_user_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_user)


def _on_user_deleted(sender, instance, **_kwargs) -> None:
    del sender
    _safe_delete("users", {"username": instance.username})
    # Cascade: drop any sidecar M2M rows + user-keyed rows. The main DB
    # cascades through Django FKs, but the sidecar has no FKs, so we
    # do it explicitly.
    _safe_delete("user_groups", {"username": instance.username})
    _safe_delete("bookmarks", {"username": instance.username})
    _safe_delete("favorites", {"username": instance.username})
    _safe_delete("settings_browser", {"username": instance.username})
    _safe_delete("settings_filters", {"username": instance.username})
    _safe_delete("settings_last_route", {"username": instance.username})


def _on_user_auth_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_user_auth)


def _on_group_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_group)


def _on_group_deleted(sender, instance, **_kwargs) -> None:
    del sender
    _safe_delete("groups", {"name": instance.name})
    _safe_delete("user_groups", {"group_name": instance.name})
    _safe_delete("library_groups", {"group_name": instance.name})


def _on_group_auth_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_group_auth)


def _on_library_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_library)


def _on_library_deleted(sender, instance, **_kwargs) -> None:
    del sender
    path = str(instance.path)
    _safe_delete("libraries", {"path": path})
    _safe_delete("library_groups", {"library_path": path})


def _on_bookmark_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_bookmark)


def _on_bookmark_deleted(sender, instance, **_kwargs) -> None:
    del sender
    if instance.user_id is None:
        return
    try:
        username = instance.user.username
        comic_path = str(instance.comic.path)
    except Exception:
        logger.exception("Sidecar bookmark-delete identifier resolution failed")
        return
    _safe_delete("bookmarks", {"username": username, "comic_path": comic_path})


# Favorite delete is the tricky case — see module docstring on the
# ``_on_favorite_target_deleted`` extension below.


def _on_favorite_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_favorite)


def _on_favorite_deleted(sender, instance, **_kwargs) -> None:
    """
    Mirror a Favorite delete to the sidecar.

    The favorited target row may already be gone (cascade delete). In
    that path the dedicated handler :func:`_on_favorite_target_deleted`
    runs first and clears the sidecar rows by target identifier, so
    this handler's lookup-and-skip is a no-op. The user-initiated
    "un-favorite" path (target still alive) resolves cleanly here.
    """
    del sender
    from codex.models.favorite import FAVORITE_MODEL_GROUP_CODES

    target_model = None
    for model, code in FAVORITE_MODEL_GROUP_CODES.items():
        if code == instance.group:
            target_model = model
            break
    if target_model is None:
        return
    target = target_model.objects.filter(pk=instance.target_id).first()
    if target is None:
        # Target already deleted — cascade handler already cleared rows.
        return
    try:
        parts = identifier_for_browse_group(instance.group, target)
        identifier_json = encode_identifier(instance.group, parts)
        username = instance.user.username
    except Exception:
        logger.exception("Sidecar favorite-delete identifier resolution failed")
        return
    _safe_delete(
        "favorites",
        {
            "username": username,
            "group_char": instance.group,
            "identifier_json": identifier_json,
        },
    )


def _on_favorite_target_deleted(sender, instance, **_kwargs) -> None:
    """
    Mirror cascade-deletion of a browse-group target into the sidecar.

    Connected for every ``sender`` in ``FAVORITE_MODEL_GROUP_CODES`` and
    fires *before* the main-DB favorite rows are cascade-deleted, so we
    can still resolve the target's identifier. Removes *every* user's
    favorite of that target (the polymorphic identifier doesn't carry
    user-scope).
    """
    from codex.models.favorite import FAVORITE_MODEL_GROUP_CODES

    group_char = FAVORITE_MODEL_GROUP_CODES.get(sender)
    if group_char is None:
        return
    try:
        parts = identifier_for_browse_group(group_char, instance)
        identifier_json = encode_identifier(group_char, parts)
    except Exception:
        logger.exception(
            f"Sidecar favorite-cascade identifier resolution failed for {sender.__name__}"
        )
        return
    _safe_delete(
        "favorites",
        {"group_char": group_char, "identifier_json": identifier_json},
    )


def _on_settings_browser_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_settings_browser)


def _on_settings_browser_deleted(sender, instance, **_kwargs) -> None:
    del sender
    if instance.user_id is None:
        return
    try:
        username = instance.user.username
    except Exception:
        logger.exception("Sidecar settings-browser identifier resolution failed")
        return
    where = {"username": username, "client": instance.client, "name": instance.name}
    _safe_delete("settings_browser", where)
    _safe_delete("settings_filters", where)
    _safe_delete("settings_last_route", where)


def _on_settings_filters_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_settings_filters)


def _on_settings_last_route_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_settings_last_route)


def _on_admin_flag_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_admin_flag)


def _on_admin_flag_deleted(sender, instance, **_kwargs) -> None:
    del sender
    _safe_delete("admin_flags", {"key": instance.key})


def _on_timestamp_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_timestamp)


def _on_timestamp_deleted(sender, instance, **_kwargs) -> None:
    del sender
    _safe_delete("timestamps", {"key": instance.key})


def _on_tagging_defaults_saved(sender, instance, **_kwargs) -> None:
    del sender
    _safe_upsert(instance, serializers.serialize_tagging_defaults)


# ── M2M handlers ─────────────────────────────────────────────────────


def _user_groups_changed(sender, instance, action, pk_set, **_kwargs) -> None:
    """Track Django auth User.groups M2M membership."""
    del sender
    from django.contrib.auth.models import Group

    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    username = instance.username
    if action == "post_clear":
        _safe_delete("user_groups", {"username": username})
        return
    group_names = list(
        Group.objects.filter(pk__in=pk_set or ()).values_list("name", flat=True)
    )
    for name in group_names:
        if action == "post_add":
            try:
                get_store().upsert(
                    "user_groups",
                    ("username", "group_name"),
                    {"username": username, "group_name": name},
                )
            except Exception:
                logger.exception("Sidecar user_groups upsert failed")
        else:
            _safe_delete("user_groups", {"username": username, "group_name": name})


def _library_groups_changed(sender, instance, action, pk_set, **_kwargs) -> None:
    """Track Library.groups M2M membership."""
    del sender
    from django.contrib.auth.models import Group

    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    library_path = str(instance.path)
    if action == "post_clear":
        _safe_delete("library_groups", {"library_path": library_path})
        return
    group_names = list(
        Group.objects.filter(pk__in=pk_set or ()).values_list("name", flat=True)
    )
    for name in group_names:
        if action == "post_add":
            try:
                get_store().upsert(
                    "library_groups",
                    ("library_path", "group_name"),
                    {"library_path": library_path, "group_name": name},
                )
            except Exception:
                logger.exception("Sidecar library_groups upsert failed")
        else:
            _safe_delete(
                "library_groups",
                {"library_path": library_path, "group_name": name},
            )


# ── Registration ─────────────────────────────────────────────────────


def connect_user_data_signals() -> None:
    """
    Wire post_save / post_delete / m2m_changed handlers.

    Called from :func:`codex.signals.django_signals.connect_signals`
    after ``django.setup()``. Idempotent: Django's ``Signal.connect``
    de-duplicates by ``(receiver, sender)``.
    """
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from django.db.models.signals import (
        m2m_changed,
        post_delete,
        post_save,
    )

    from codex.models.admin import (
        AdminFlag,
        ComicboxTaggingDefaults,
        Timestamp,
    )
    from codex.models.auth import GroupAuth, UserAuth
    from codex.models.bookmark import Bookmark
    from codex.models.favorite import FAVORITE_MODEL_GROUP_CODES, Favorite
    from codex.models.library import Library
    from codex.models.settings import (
        SettingsBrowser,
        SettingsBrowserFilters,
        SettingsBrowserLastRoute,
    )

    user_model = get_user_model()

    post_save.connect(_on_user_saved, sender=user_model)
    post_delete.connect(_on_user_deleted, sender=user_model)
    post_save.connect(_on_user_auth_saved, sender=UserAuth)
    post_save.connect(_on_group_saved, sender=Group)
    post_delete.connect(_on_group_deleted, sender=Group)
    post_save.connect(_on_group_auth_saved, sender=GroupAuth)
    post_save.connect(_on_library_saved, sender=Library)
    post_delete.connect(_on_library_deleted, sender=Library)
    post_save.connect(_on_bookmark_saved, sender=Bookmark)
    post_delete.connect(_on_bookmark_deleted, sender=Bookmark)
    post_save.connect(_on_favorite_saved, sender=Favorite)
    post_delete.connect(_on_favorite_deleted, sender=Favorite)
    post_save.connect(_on_settings_browser_saved, sender=SettingsBrowser)
    post_delete.connect(_on_settings_browser_deleted, sender=SettingsBrowser)
    post_save.connect(_on_settings_filters_saved, sender=SettingsBrowserFilters)
    post_save.connect(_on_settings_last_route_saved, sender=SettingsBrowserLastRoute)
    post_save.connect(_on_admin_flag_saved, sender=AdminFlag)
    post_delete.connect(_on_admin_flag_deleted, sender=AdminFlag)
    post_save.connect(_on_timestamp_saved, sender=Timestamp)
    post_delete.connect(_on_timestamp_deleted, sender=Timestamp)
    post_save.connect(_on_tagging_defaults_saved, sender=ComicboxTaggingDefaults)

    # Pre-cascade favorite cleanup: fires for every browse-group target
    # *before* its post_delete kicks in :func:`_on_favorite_target_deleted`
    # in :mod:`codex.signals.django_signals` (which then cascades the
    # actual Favorite rows). The order keeps the target instance alive
    # when we resolve its identifier.
    from django.db.models.signals import pre_delete

    for sender in FAVORITE_MODEL_GROUP_CODES:
        pre_delete.connect(_on_favorite_target_deleted, sender=sender)

    # M2M memberships.
    m2m_changed.connect(_user_groups_changed, sender=user_model.groups.through)
    m2m_changed.connect(_library_groups_changed, sender=Library.groups.through)

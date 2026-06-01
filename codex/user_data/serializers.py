"""
Per-model row → sidecar dict converters.

Each ``serialize_*`` callable takes a main-DB model instance and returns
``(table_name, key_columns, data_dict)`` ready to feed
:meth:`SidecarStore.upsert`. Foreign keys are resolved to stable
identifiers (usernames, comic paths, group name-chains, tag names) so
the sidecar survives a main-DB rebuild.

These functions assume the instance is fully populated (saved) and that
related FKs are loaded. Signal handlers (the only callers) get this
for free from ``post_save``.

Failures are caller's problem: serializers may raise on missing FKs or
unexpected shapes. Signal handlers wrap calls and log without
re-raising.
"""

from __future__ import annotations

import json
from typing import Any

from codex.collection import Collection
from codex.user_data.identifiers import (
    FILTER_TAG_COLUMNS,
    encode_identifier,
    identifier_for_browse_group,
    tag_model_for_filter,
)


def _datetime_str(value: Any) -> str | None:
    """Stringify a datetime for SQLite TEXT storage; return None for None."""
    return None if value is None else value.isoformat()


# ── User / auth ──────────────────────────────────────────────────────


def serialize_user(user) -> tuple[str, tuple[str, ...], dict[str, Any]]:
    """User row — UserAuth fields (OneToOne) are merged in if loaded."""
    age_rating_name: str | None = None
    user_auth = getattr(user, "userauth", None)
    if user_auth is not None and user_auth.age_rating_metron_id is not None:
        # Resolve the FK to its name without an extra query when the
        # related row is already cached on the instance.
        age_rating_name = user_auth.age_rating_metron.name
    return (
        "users",
        ("username",),
        {
            "username": user.username,
            "password": user.password,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_staff": int(user.is_staff),
            "is_superuser": int(user.is_superuser),
            "is_active": int(user.is_active),
            "date_joined": _datetime_str(user.date_joined),
            "last_login": _datetime_str(user.last_login),
            "age_rating_metron_name": age_rating_name,
            "updated_at": _datetime_str(getattr(user, "updated_at", None)),
        },
    )


def serialize_group(group) -> tuple[str, tuple[str, ...], dict[str, Any]]:
    """Auth Group row, with permissions and the GroupAuth.exclude flag."""
    permissions = sorted(
        f"{perm.content_type.app_label}.{perm.codename}"
        for perm in group.permissions.all()
    )
    group_auth = getattr(group, "groupauth", None)
    exclude = bool(group_auth.exclude) if group_auth is not None else False
    return (
        "groups",
        ("name",),
        {
            "name": group.name,
            "permissions": json.dumps(permissions, separators=(",", ":")),
            "exclude": int(exclude),
            "updated_at": None,
        },
    )


# ── Library ──────────────────────────────────────────────────────────


def serialize_library(library) -> tuple[str, tuple[str, ...], dict[str, Any]]:
    """Library scalar columns; M2M ``groups`` is handled by a separate signal."""
    # ``poll_every`` is a DurationField (timedelta). ``str(timedelta)``
    # produces ``"1 day, 0:00:00"`` style output that DurationField can't
    # round-trip on read. Store total seconds and reconstruct on restore.
    poll_every = library.poll_every
    poll_every_seconds = None if poll_every is None else poll_every.total_seconds()
    return (
        "libraries",
        ("path",),
        {
            "path": str(library.path),
            "events": int(library.events),
            "poll": int(library.poll),
            "poll_every": (
                None if poll_every_seconds is None else str(poll_every_seconds)
            ),
            "last_poll": _datetime_str(library.last_poll),
            "updated_at": _datetime_str(getattr(library, "updated_at", None)),
        },
    )


# ── Bookmark / Favorite ──────────────────────────────────────────────


def serialize_bookmark(
    bookmark,
) -> tuple[str, tuple[str, ...], dict[str, Any]] | None:
    """
    Bookmark row keyed by ``(username, comic_path)``.

    Anonymous (``user IS NULL``) bookmarks are ephemeral by design —
    they get a synthetic session id from Django, not a persistent
    user. Returning ``None`` tells the signal handler to skip the
    sidecar write.
    """
    if bookmark.user_id is None:
        return None
    return (
        "bookmarks",
        ("username", "comic_path"),
        {
            "username": bookmark.user.username,
            "comic_path": str(bookmark.comic.path),
            "page": bookmark.page,
            "finished": int(bool(bookmark.finished)),
            "updated_at": _datetime_str(getattr(bookmark, "updated_at", None)),
        },
    )


def serialize_favorite(
    favorite,
) -> tuple[str, tuple[str, ...], dict[str, Any]] | None:
    """
    Favorite row keyed by ``(username, collection, identifier_json)``.

    The polymorphic ``(group, target_id)`` pair is resolved into a stable
    name-chain identifier via :func:`identifier_for_browse_group`.
    Resolution may fail (target deleted between signal queue and write) —
    return ``None`` to skip rather than crash.
    """
    from codex.models.favorite import FAVORITE_MODEL_GROUP_CODES

    target_model = None
    for model, code in FAVORITE_MODEL_GROUP_CODES.items():
        if code == favorite.group:
            target_model = model
            break
    if target_model is None:
        return None
    instance = target_model.objects.filter(pk=favorite.target_id).first()
    if instance is None:
        return None
    parts = identifier_for_browse_group(favorite.group, instance)
    return (
        "favorites",
        ("username", "collection", "identifier_json"),
        {
            "username": favorite.user.username,
            "collection": favorite.group,
            "identifier_json": encode_identifier(favorite.group, parts),
            "updated_at": _datetime_str(getattr(favorite, "updated_at", None)),
        },
    )


# ── Browser settings ─────────────────────────────────────────────────


def serialize_settings_browser(
    browser,
) -> tuple[str, tuple[str, ...], dict[str, Any]] | None:
    """
    Browser-settings row. Skip anonymous-session rows (no username).

    The shared ``show`` FK is flattened into ``show_p/i/s/v``.
    """
    if browser.user_id is None:
        return None
    show = browser.show
    return (
        "settings_browser",
        ("username", "client", "name"),
        {
            "username": browser.user.username,
            "client": browser.client,
            "name": browser.name,
            "top_group": browser.top_group,
            "order_by": browser.order_by,
            "order_reverse": int(browser.order_reverse),
            "order_extra_keys": json.dumps(
                browser.order_extra_keys, separators=(",", ":")
            ),
            "search": browser.search,
            "custom_covers": int(browser.custom_covers),
            "dynamic_covers": int(browser.dynamic_covers),
            "twenty_four_hour_time": int(browser.twenty_four_hour_time),
            "always_show_filename": int(browser.always_show_filename),
            "view_mode": browser.view_mode,
            "table_columns": json.dumps(browser.table_columns, separators=(",", ":")),
            "table_cover_size": browser.table_cover_size,
            "show_p": int(show.p),
            "show_i": int(show.i),
            "show_s": int(show.s),
            "show_v": int(show.v),
            "updated_at": _datetime_str(getattr(browser, "updated_at", None)),
        },
    )


def _rewrite_filter_value(column: str, value: Any) -> Any:
    """
    Convert a SettingsBrowserFilters JSONField value for sidecar storage.

    Tag-PK columns (see :data:`FILTER_TAG_COLUMNS`) hold ``[pk, ...]``
    in the main DB; the sidecar stores ``[name, ...]``. Unknown PKs
    silently drop out of the list rather than poison the sidecar row.
    Scalar columns (year, decade, file_type, ...) pass through.
    """
    if column not in FILTER_TAG_COLUMNS:
        return value
    if not value:
        return []
    model = tag_model_for_filter(column)
    if model is None:
        return value
    # Every tag model inherits ``NamedModel.name``; missing PKs drop
    # silently rather than raise.
    return list(model.objects.filter(pk__in=value).values_list("name", flat=True))


def serialize_settings_filters(
    filters,
) -> tuple[str, tuple[str, ...], dict[str, Any]] | None:
    """Filter row, with tag-PK columns rewritten to tag-name lists."""
    browser = filters.browser
    if browser.user_id is None:
        return None
    from codex.models.settings import SettingsBrowserFilters

    data: dict[str, Any] = {
        "username": browser.user.username,
        "client": browser.client,
        "name": browser.name,
        "bookmark": filters.bookmark,
        "favorite": int(bool(filters.favorite)),
    }
    for column in SettingsBrowserFilters.FILTER_KEYS:
        if column in {"bookmark", "favorite"}:
            continue
        raw = getattr(filters, column)
        rewritten = _rewrite_filter_value(column, raw)
        data[column] = json.dumps(rewritten, separators=(",", ":"))
    return ("settings_filters", ("username", "client", "name"), data)


def serialize_settings_last_route(
    last_route,
) -> tuple[str, tuple[str, ...], dict[str, Any]] | None:
    """
    Last-route row.

    The ``pks`` list holds main-DB PKs for whatever group the user was
    last browsing. We resolve each PK to a name-chain identifier so
    restore can find the row again post-rebuild.
    """
    browser = last_route.browser
    if browser.user_id is None:
        return None
    pks_resolved = _resolve_last_route_pks(last_route.group, last_route.pks)
    return (
        "settings_last_route",
        ("username", "client", "name"),
        {
            "username": browser.user.username,
            "client": browser.client,
            "name": browser.name,
            "collection": last_route.group,
            "pks_json": json.dumps(pks_resolved, separators=(",", ":")),
            "page": last_route.page,
        },
    )


def _resolve_last_route_pks(group: str, pks: list[int]) -> list[list[Any]]:
    """Resolve a list of browse-group PKs to identifier parts; missing rows drop."""
    if not pks:
        return []
    if group == Collection.ROOT:
        # Root pseudo-group — no PKs to resolve.
        return []
    from codex.models.favorite import FAVORITE_MODEL_GROUP_CODES

    target_model = None
    for model, code in FAVORITE_MODEL_GROUP_CODES.items():
        if code == group:
            target_model = model
            break
    if target_model is None:
        return []
    by_pk = {obj.pk: obj for obj in target_model.objects.filter(pk__in=pks)}
    resolved: list[list[Any]] = []
    for pk in pks:
        obj = by_pk.get(pk)
        if obj is None:
            continue
        try:
            resolved.append(identifier_for_browse_group(group, obj))
        except ValueError:
            continue
    return resolved


# ── Admin / timestamp / tagging defaults ─────────────────────────────


def serialize_admin_flag(flag) -> tuple[str, tuple[str, ...], dict[str, Any]]:
    """AdminFlag row, with the age-rating FK resolved to a name."""
    age_rating_name: str | None = None
    if flag.age_rating_metron_id is not None:
        age_rating_name = flag.age_rating_metron.name
    return (
        "admin_flags",
        ("key",),
        {
            "key": flag.key,
            "on_flag": int(bool(flag.on)),
            "value": flag.value,
            "age_rating_metron_name": age_rating_name,
            "updated_at": _datetime_str(getattr(flag, "updated_at", None)),
        },
    )


def serialize_timestamp(ts) -> tuple[str, tuple[str, ...], dict[str, Any]]:
    """Timestamp row."""
    return (
        "timestamps",
        ("key",),
        {
            "key": ts.key,
            "value": ts.value,
            "updated_at": _datetime_str(getattr(ts, "updated_at", None)),
        },
    )


def serialize_tagging_defaults(
    defaults,
) -> tuple[str, tuple[str, ...], dict[str, Any]]:
    """ComicboxTaggingDefaults singleton — always pk=1 in main DB."""
    return (
        "tagging_defaults",
        ("pk",),
        {
            "pk": 1,
            "default_formats": json.dumps(
                defaults.default_formats, separators=(",", ":")
            ),
            "delete_original": int(bool(defaults.delete_original)),
            "default_match_mode": defaults.default_match_mode,
            "default_prompts_mode": defaults.default_prompts_mode,
            "default_sources": json.dumps(
                defaults.default_sources, separators=(",", ":")
            ),
            "prompt_timeout_seconds": defaults.prompt_timeout_seconds,
            "metron_user": defaults.metron_user or "",
            "metron_password": defaults.metron_password or "",
            "metron_url": defaults.metron_url or "",
            "comicvine_key": defaults.comicvine_key or "",
            "comicvine_url": defaults.comicvine_url or "",
            "updated_at": _datetime_str(getattr(defaults, "updated_at", None)),
        },
    )

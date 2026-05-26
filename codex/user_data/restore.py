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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

from codex.user_data.store import SidecarStore, get_store

if TYPE_CHECKING:
    from pathlib import Path


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
    Restore the main DB from the sidecar.

    ``sidecar_path`` lets callers point at an alternate file (e.g. a
    user-supplied backup); defaults to the process-wide store. ``dry_run``
    walks every row and resolves identifiers but doesn't write — useful
    for "what would happen" reporting.
    """
    store = SidecarStore(sidecar_path) if sidecar_path is not None else get_store()
    report = RestoreReport()
    _restore_groups(store, report, dry_run=dry_run)
    _restore_users(store, report, dry_run=dry_run)
    _restore_user_groups(store, report, dry_run=dry_run)
    _restore_libraries(store, report, dry_run=dry_run)
    _restore_library_groups(store, report, dry_run=dry_run)
    _restore_admin_flags(store, report, dry_run=dry_run)
    _restore_timestamps(store, report, dry_run=dry_run)
    _restore_tagging_defaults(store, report, dry_run=dry_run)
    _restore_bookmarks(store, report, dry_run=dry_run)
    _restore_favorites(store, report, dry_run=dry_run)
    _restore_settings_browser(store, report, dry_run=dry_run)
    return report


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
            defaults={
                "password": row["password"] or "",
                "email": row["email"] or "",
                "first_name": row["first_name"] or "",
                "last_name": row["last_name"] or "",
                "is_staff": bool(row["is_staff"]),
                "is_superuser": bool(row["is_superuser"]),
                "is_active": bool(row["is_active"]),
                "date_joined": row["date_joined"] or None,
                "last_login": row["last_login"] or None,
            },
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
    import datetime

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
            defaults["poll_every"] = datetime.timedelta(
                seconds=float(row["poll_every"])
            )
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
        Timestamp.objects.update_or_create(
            key=row["key"], defaults={"version": row["version"] or ""}
        )
        report.note_written("timestamps")


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
    defaults = {
        "default_formats": json.loads(row["default_formats"] or "[]"),
        "delete_original": bool(row["delete_original"]),
        "default_match_mode": row["default_match_mode"] or "auto",
        "default_prompts_mode": row["default_prompts_mode"] or "ask",
        "default_sources": json.loads(row["default_sources"] or "[]"),
        "prompt_timeout_seconds": row["prompt_timeout_seconds"] or 3600,
        "metron_user": row["metron_user"] or "",
        "metron_password": row["metron_password"] or "",
        "metron_url": row["metron_url"] or "",
        "comicvine_key": row["comicvine_key"] or "",
        "comicvine_url": row["comicvine_url"] or "",
        "active_session_id": row["active_session_id"] or "",
        "active_prompts": json.loads(row["active_prompts"] or "[]"),
    }
    ComicboxTaggingDefaults.objects.update_or_create(pk=1, defaults=defaults)
    report.note_written("tagging_defaults")


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
        comic = Comic.objects.filter(path=row["comic_path"]).first()
        if comic is None:
            report.note_skipped("bookmarks", f"missing comic {row['comic_path']!r}")
            continue
        Bookmark.objects.update_or_create(
            user=user,
            session=None,
            comic=comic,
            defaults={"page": row["page"], "finished": bool(row["finished"])},
        )
        report.note_written("bookmarks")


def _restore_favorites(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Restore Favorite rows; resolve identifier_json → main-DB PK."""
    from django.contrib.auth import get_user_model

    from codex.models.favorite import FAVORITE_MODEL_GROUP_CODES, Favorite

    user_model = get_user_model()
    code_to_model = {code: model for model, code in FAVORITE_MODEL_GROUP_CODES.items()}
    for row in store.fetchall("favorites"):
        if dry_run:
            report.note_written("favorites")
            continue
        user = user_model.objects.filter(username=row["username"]).first()
        if user is None:
            report.note_skipped("favorites", f"missing user {row['username']!r}")
            continue
        group_char = row["group_char"]
        target_model = code_to_model.get(group_char)
        if target_model is None:
            report.note_skipped("favorites", f"unknown group_char {group_char!r}")
            continue
        decoded = json.loads(row["identifier_json"])
        # decoded == [group_char, ...parts]
        parts = decoded[1:]
        target_pk = _resolve_browse_group_pk(group_char, parts, target_model)
        if target_pk is None:
            username = row["username"]
            report.note_skipped(
                "favorites",
                f"unresolvable {group_char!r} target {parts!r} for user {username!r}",
            )
            continue
        Favorite.objects.update_or_create(
            user=user, group=group_char, target_id=target_pk
        )
        report.note_written("favorites")


def _resolve_browse_group_pk(group_char: str, parts: list[Any], model) -> int | None:
    """Resolve a name-chain identifier back to a main-DB PK."""
    match group_char:
        case "c" | "f":
            obj = model.objects.filter(path=parts[0]).first()
        case "p" | "a":
            obj = model.objects.filter(name=parts[0]).first()
        case "i":
            obj = model.objects.filter(publisher__name=parts[0], name=parts[1]).first()
        case "s":
            obj = model.objects.filter(
                publisher__name=parts[0],
                imprint__name=parts[1],
                name=parts[2],
            ).first()
        case "v":
            obj = model.objects.filter(
                publisher__name=parts[0],
                imprint__name=parts[1],
                series__name=parts[2],
                name=parts[3],
                number_to=parts[4],
            ).first()
        case _:
            return None
    return None if obj is None else obj.pk


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


def _build_browser_defaults(row, show) -> dict[str, Any]:
    """Map a sidecar settings_browser row to ``update_or_create`` defaults."""
    return {
        "show": show,
        "top_group": row["top_group"] or "",
        "order_by": row["order_by"] or "",
        "order_reverse": bool(row["order_reverse"]),
        "order_extra_keys": json.loads(row["order_extra_keys"] or "[]"),
        "search": row["search"] or "",
        "custom_covers": bool(row["custom_covers"]),
        "dynamic_covers": bool(row["dynamic_covers"]),
        "twenty_four_hour_time": bool(row["twenty_four_hour_time"]),
        "always_show_filename": bool(row["always_show_filename"]),
        "view_mode": row["view_mode"] or "",
        "table_columns": json.loads(row["table_columns"] or "{}"),
        "table_cover_size": row["table_cover_size"] or "",
    }


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
        p=bool(row["show_p"]),
        i=bool(row["show_i"]),
        s=bool(row["show_s"]),
        v=bool(row["show_v"]),
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


def _restore_one_filter(row, browser, report: RestoreReport) -> None:
    """Resolve tag-name lists in the sidecar back to PK lists."""
    from codex.models.settings import SettingsBrowserFilters
    from codex.user_data.identifiers import (
        FILTER_TAG_COLUMNS,
        tag_model_for_filter,
    )

    defaults: dict[str, Any] = {
        "bookmark": row["bookmark"] or "",
        "favorite": bool(row["favorite"]),
    }
    for column in SettingsBrowserFilters.FILTER_KEYS:
        if column in {"bookmark", "favorite"}:
            continue
        raw = json.loads(row[column] or "[]")
        if column in FILTER_TAG_COLUMNS:
            model = tag_model_for_filter(column)
            if model is None:
                defaults[column] = []
                continue
            pks = list(model.objects.filter(name__in=raw).values_list("pk", flat=True))
            if len(pks) != len(raw):
                dropped = len(raw) - len(pks)
                report.note_skipped(
                    "settings_filters",
                    f"dropped {dropped} {column} tag(s) unmatched for {browser.user.username}",
                )
            defaults[column] = pks
        else:
            defaults[column] = raw
    SettingsBrowserFilters.objects.update_or_create(browser=browser, defaults=defaults)
    report.note_written("settings_filters")


def _resolve_last_route_pks(
    group_char: str, decoded: list, report: RestoreReport
) -> list[int]:
    """Map sidecar identifier tuples to main-DB PKs; missing rows drop + log."""
    if group_char == "r" or not decoded:
        return []
    from codex.models.favorite import FAVORITE_MODEL_GROUP_CODES

    target_model = next(
        (m for m, c in FAVORITE_MODEL_GROUP_CODES.items() if c == group_char),
        None,
    )
    if target_model is None:
        return []
    pks: list[int] = []
    for parts in decoded:
        pk = _resolve_browse_group_pk(group_char, parts, target_model)
        if pk is None:
            report.note_skipped(
                "settings_last_route",
                f"unresolvable last-route {group_char!r} target {parts!r}",
            )
            continue
        pks.append(pk)
    return pks


def _restore_one_last_route(row, browser, report: RestoreReport) -> None:
    """Restore a single ``settings_last_route`` row."""
    from codex.models.settings import SettingsBrowserLastRoute

    group_char = row["group_char"]
    decoded = json.loads(row["pks_json"] or "[]")
    pks = _resolve_last_route_pks(group_char, decoded, report)
    SettingsBrowserLastRoute.objects.update_or_create(
        browser=browser,
        defaults={"group": group_char, "pks": pks, "page": row["page"] or 1},
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

"""Notifier Tasks."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from django.utils import timezone

from codex.choices.notifications import Notifications
from codex.librarian.tasks import LibrarianTask
from codex.websockets.consumers import ChannelGroups


@dataclass(frozen=True)
class NotifierTask(LibrarianTask):
    """
    Handle with the Notifier.

    ``mtime`` and ``scope`` ride the v4 typed WebSocket payload so
    clients can skip the ``loadMtimes()`` probe after a notification
    ("kill the two-step" from ``tasks/api-v4.md``). v3 callers ignored
    both; v4 reads them. ``mtime`` is epoch-milliseconds (matches the
    frontend's ``Date.now()``); ``scope`` is a free-form dict whose
    keys depend on the notification type (e.g. ``{libraryIds: [...]}``
    for ``library.changed``).

    The dataclass is frozen so the module-level constants below can
    be safely reused across processes; the factory helpers
    (:func:`library_changed_task`, etc.) build fresh enriched
    instances at call sites.
    """

    text: str
    group: str
    mtime: int | None = None
    scope: Mapping[str, Any] = field(default_factory=dict)


def _now_ms() -> int:
    """Return current epoch milliseconds (matches the frontend ``Date.now()``)."""
    return int(timezone.now().timestamp() * 1000)


def _ts_ms(dt) -> int | None:
    """Convert a datetime to epoch milliseconds, or ``None`` if absent."""
    return int(dt.timestamp() * 1000) if dt else None


# ── Constants for callers with no scope/mtime context ─────────────────
# These match the v3 enqueue shape exactly and are safe to share
# (frozen dataclass + immutable default scope dict). Sites that *do*
# know scope/mtime should use the factory helpers below instead.

ADMIN_FLAGS_CHANGED_TASK = NotifierTask(
    Notifications.ADMIN_FLAGS.value, ChannelGroups.ALL
)
COVERS_CHANGED_TASK = NotifierTask(Notifications.COVERS.value, ChannelGroups.ALL)
FAILED_IMPORTS_CHANGED_TASK = NotifierTask(
    Notifications.FAILED_IMPORTS.value, ChannelGroups.ADMIN
)
GROUPS_CHANGED_TASK = NotifierTask(Notifications.GROUPS.value, ChannelGroups.ALL)
LIBRARIAN_STATUS_TASK = NotifierTask(
    Notifications.LIBRARIAN_STATUS.value, ChannelGroups.ADMIN
)
LIBRARY_CHANGED_TASK = NotifierTask(Notifications.LIBRARY.value, ChannelGroups.ALL)
ONLINE_TAG_PROMPT_TASK = NotifierTask(
    Notifications.ONLINE_TAG_PROMPT.value, ChannelGroups.ADMIN
)
USERS_CHANGED_TASK = NotifierTask(Notifications.USERS.value, ChannelGroups.ALL)
ADMIN_USERS_CHANGED_TASK = NotifierTask(Notifications.USERS.value, ChannelGroups.ADMIN)


# ── Factory helpers that enrich the constants with scope/mtime ────────


def library_changed_task(library) -> NotifierTask:
    """Build a ``LIBRARY_CHANGED`` task scoped to one library."""
    return replace(
        LIBRARY_CHANGED_TASK,
        mtime=_ts_ms(getattr(library, "updated_at", None)) or _now_ms(),
        scope={"libraryIds": [library.pk]},
    )


def failed_imports_changed_task(library=None) -> NotifierTask:
    """Build a ``FAILED_IMPORTS`` task, scoped to one library when known."""
    scope: dict[str, Any] = {}
    mtime: int | None = None
    if library is not None:
        scope["libraryIds"] = [library.pk]
        mtime = _ts_ms(getattr(library, "updated_at", None))
    return replace(
        FAILED_IMPORTS_CHANGED_TASK, mtime=mtime or _now_ms(), scope=scope
    )


def covers_changed_task(
    *, collection: str | None = None, ids: Iterable[int] | None = None
) -> NotifierTask:
    """Build a ``COVERS_CHANGED`` task with optional collection+ids scope."""
    scope: dict[str, Any] = {}
    if collection:
        scope["collection"] = collection
    if ids is not None:
        scope["ids"] = sorted(set(ids))
    return replace(COVERS_CHANGED_TASK, mtime=_now_ms(), scope=scope)


def bookmark_changed_task(user_id: int, comic_ids: Iterable[int]) -> NotifierTask:
    """Build a ``BOOKMARK_CHANGED`` task targeted to one user's channel."""
    return NotifierTask(
        text=Notifications.BOOKMARK.value,
        group=f"user_{user_id}",
        mtime=_now_ms(),
        scope={"comicIds": sorted(set(comic_ids))},
    )


def admin_flags_changed_task(*, keys: Iterable[str] | None = None) -> NotifierTask:
    """Build an ``ADMIN_FLAGS_CHANGED`` task, optionally scoped to keys."""
    scope: dict[str, Any] = {}
    if keys is not None:
        scope["flagKeys"] = sorted(set(keys))
    return replace(ADMIN_FLAGS_CHANGED_TASK, mtime=_now_ms(), scope=scope)


def groups_changed_task(*, ids: Iterable[int] | None = None) -> NotifierTask:
    """Build a ``GROUPS_CHANGED`` task, optionally scoped to group ids."""
    scope: dict[str, Any] = {}
    if ids is not None:
        scope["groupIds"] = sorted(set(ids))
    return replace(GROUPS_CHANGED_TASK, mtime=_now_ms(), scope=scope)


def users_changed_task(
    *, uid: int | None = None, ids: Iterable[int] | None = None
) -> NotifierTask:
    """
    Build a ``USERS_CHANGED`` task.

    Per-user changes go to that user's private channel; admin-visible
    changes broadcast to the ADMIN channel (matches v3's split).
    """
    scope: dict[str, Any] = {}
    if ids is not None:
        scope["userIds"] = sorted(set(ids))
    if uid:
        return NotifierTask(
            text=Notifications.USERS.value,
            group=f"user_{uid}",
            mtime=_now_ms(),
            scope=scope,
        )
    return replace(ADMIN_USERS_CHANGED_TASK, mtime=_now_ms(), scope=scope)

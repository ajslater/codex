"""Notifier Tasks."""

from dataclasses import dataclass, replace

from django.utils import timezone

from codex.choices.notifications import Notifications
from codex.librarian.tasks import LibrarianTask
from codex.websockets.consumers import ChannelGroups


@dataclass(frozen=True)
class NotifierTask(LibrarianTask):
    """
    Handle with the Notifier.

    ``mtime`` rides the v4 typed WebSocket payload so the browser can
    use it as the ``library.changed`` refresh hint without a second
    ``loadMtimes()`` probe. It is epoch-milliseconds (matches the
    frontend's ``Date.now()``). v3 callers ignored it; v4 reads it.

    The dataclass is frozen so the module-level constants below can
    be safely reused across processes; the factory helpers
    (:func:`library_changed_task`, etc.) build fresh stamped
    instances at call sites.
    """

    text: str
    group: str
    mtime: int | None = None


def _now_ms() -> int:
    """Return current epoch milliseconds (matches the frontend ``Date.now()``)."""
    return int(timezone.now().timestamp() * 1000)


def _ts_ms(dt) -> int | None:
    """Convert a datetime to epoch milliseconds, or ``None`` if absent."""
    return int(dt.timestamp() * 1000) if dt else None


# ── Constants for callers with no mtime context ───────────────────────
# These match the v3 enqueue shape exactly and are safe to share
# (frozen dataclass). Sites that know an mtime use the factory helpers
# below instead.

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


# ── Factory helpers that stamp the constants with an mtime ────────────


def library_changed_task(library) -> NotifierTask:
    """Build a ``LIBRARY_CHANGED`` task carrying the library's mtime."""
    return replace(
        LIBRARY_CHANGED_TASK,
        mtime=_ts_ms(getattr(library, "updated_at", None)) or _now_ms(),
    )


def failed_imports_changed_task(library=None) -> NotifierTask:
    """Build a ``FAILED_IMPORTS`` task, stamped with the library's mtime."""
    mtime = None
    if library is not None:
        mtime = _ts_ms(getattr(library, "updated_at", None))
    return replace(FAILED_IMPORTS_CHANGED_TASK, mtime=mtime or _now_ms())


def covers_changed_task() -> NotifierTask:
    """Build a ``COVERS_CHANGED`` task."""
    return replace(COVERS_CHANGED_TASK, mtime=_now_ms())


def admin_flags_changed_task() -> NotifierTask:
    """Build an ``ADMIN_FLAGS_CHANGED`` task."""
    return replace(ADMIN_FLAGS_CHANGED_TASK, mtime=_now_ms())


def groups_changed_task() -> NotifierTask:
    """Build a ``GROUPS_CHANGED`` task."""
    return replace(GROUPS_CHANGED_TASK, mtime=_now_ms())


def users_changed_task(*, uid: int | None = None) -> NotifierTask:
    """
    Build a ``USERS_CHANGED`` task.

    Per-user changes go to that user's private channel; admin-visible
    changes broadcast to the ADMIN channel (matches v3's split).
    """
    if uid:
        return NotifierTask(
            text=Notifications.USERS.value,
            group=f"user_{uid}",
            mtime=_now_ms(),
        )
    return replace(ADMIN_USERS_CHANGED_TASK, mtime=_now_ms())

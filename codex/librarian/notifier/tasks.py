"""Notifier Tasks."""

from dataclasses import dataclass

from codex.choices.notifications import Notifications
from codex.librarian.tasks import LibrarianTask
from codex.websockets.consumers import ChannelGroups


@dataclass(frozen=True)
class NotifierTask(LibrarianTask):
    """
    Handle with the Notifier.

    A notification only signals that a class of thing changed; the
    client reacts by probing ``/api/v4/mtime`` or reloading the relevant
    table. The dataclass is frozen so the module-level constants below
    can be safely reused across processes.
    """

    text: str
    group: str


# ── Shared task constants ─────────────────────────────────────────────
# Most notifications carry no payload beyond their type, so callers
# enqueue these shared frozen instances directly. ``users_changed_task``
# is the only one that needs a per-call value (the target user channel).

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
TAG_WRITE_ERRORS_CHANGED_TASK = NotifierTask(
    Notifications.TAG_WRITE_ERRORS.value, ChannelGroups.ADMIN
)
USERS_CHANGED_TASK = NotifierTask(Notifications.USERS.value, ChannelGroups.ALL)
ADMIN_USERS_CHANGED_TASK = NotifierTask(Notifications.USERS.value, ChannelGroups.ADMIN)


def users_changed_task(*, uid: int | None = None) -> NotifierTask:
    """
    Build a ``USERS_CHANGED`` task.

    Per-user changes go to that user's private channel; admin-visible
    changes broadcast to the ADMIN channel (matches v3's split).
    """
    if uid:
        return NotifierTask(text=Notifications.USERS.value, group=f"user_{uid}")
    return ADMIN_USERS_CHANGED_TASK

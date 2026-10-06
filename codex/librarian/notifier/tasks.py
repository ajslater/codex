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

ADMIN_FLAGS_CHANGED_TASK = NotifierTask(Notifications.ADMIN_FLAGS, ChannelGroups.ALL)
COVERS_CHANGED_TASK = NotifierTask(Notifications.COVERS, ChannelGroups.ALL)
FAILED_IMPORTS_CHANGED_TASK = NotifierTask(
    Notifications.FAILED_IMPORTS, ChannelGroups.ADMIN
)
GROUPS_CHANGED_TASK = NotifierTask(Notifications.GROUPS, ChannelGroups.ALL)
LIBRARIAN_STATUS_TASK = NotifierTask(
    Notifications.LIBRARIAN_STATUS, ChannelGroups.ADMIN
)
LIBRARY_CHANGED_TASK = NotifierTask(Notifications.LIBRARY, ChannelGroups.ALL)
ONLINE_TAG_PROMPT_TASK = NotifierTask(
    Notifications.ONLINE_TAG_PROMPT, ChannelGroups.ADMIN
)
# Its own message rather than riding LIBRARIAN_STATUS: the notifier dedupes by
# text, so a dedicated one gets its own slot instead of sharing with every
# other librarian job, and the client answers it with a single snapshot fetch.
ONLINE_TAG_SNAPSHOT_TASK = NotifierTask(
    Notifications.ONLINE_TAG_SNAPSHOT, ChannelGroups.ADMIN
)
PENDING_DELETES_CHANGED_TASK = NotifierTask(
    Notifications.PENDING_DELETES, ChannelGroups.ADMIN
)
TAG_WRITE_ERRORS_CHANGED_TASK = NotifierTask(
    Notifications.TAG_WRITE_ERRORS, ChannelGroups.ADMIN
)
USERS_CHANGED_TASK = NotifierTask(Notifications.USERS, ChannelGroups.ALL)
ADMIN_USERS_CHANGED_TASK = NotifierTask(Notifications.USERS, ChannelGroups.ADMIN)


def users_changed_task(*, uid: int | None = None) -> NotifierTask:
    """
    Build a ``USERS_CHANGED`` task.

    Per-user changes go to that user's private channel; admin-visible
    changes broadcast to the ADMIN channel (matches v3's split).
    """
    if uid:
        return NotifierTask(text=Notifications.USERS, group=f"user_{uid}")
    return ADMIN_USERS_CHANGED_TASK

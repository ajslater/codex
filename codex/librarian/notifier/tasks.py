"""Notifier Tasks."""

from dataclasses import dataclass

from codex.choices.notifications import Notifications
from codex.librarian.tasks import LibrarianTask
from codex.websockets.consumers import ChannelGroups


@dataclass
class NotifierTask(LibrarianTask):
    """Handle with the Notifier."""

    text: str
    group: str


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
USERS_CHANGED_TASK = NotifierTask(Notifications.USERS.value, ChannelGroups.ALL)
ADMIN_USERS_CHANGED_TASK = NotifierTask(Notifications.USERS.value, ChannelGroups.ADMIN)

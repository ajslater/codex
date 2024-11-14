"""Notifier Tasks."""

from dataclasses import dataclass

from codex.choices.notifications import Notifications
from codex.websockets.consumers import ChannelGroups


@dataclass
class NotifierTask:
    """Handle with the Notifier."""

    text: str
    group: str


ADMIN_FLAGS_CHANGED_TASK = NotifierTask(
    Notifications.ADMIN_FLAGS.value, ChannelGroups.ALL.name
)
COVERS_CHANGED_TASK = NotifierTask(Notifications.COVERS.value, ChannelGroups.ALL.name)
FAILED_IMPORTS_CHANGED_TASK = NotifierTask(
    Notifications.FAILED_IMPORTS.value, ChannelGroups.ADMIN.name
)
GROUPS_CHANGED_TASK = NotifierTask(Notifications.GROUPS.value, ChannelGroups.ALL.name)
LIBRARIAN_STATUS_TASK = NotifierTask(
    Notifications.LIBRARIAN_STATUS.value, ChannelGroups.ADMIN.name
)
LIBRARY_CHANGED_TASK = NotifierTask(Notifications.LIBRARY.value, ChannelGroups.ALL.name)
USERS_CHANGED_TASK = NotifierTask(Notifications.USERS.value, ChannelGroups.ALL.name)
ADMIN_USERS_CHANGED_TASK = NotifierTask(
    Notifications.USERS.value, ChannelGroups.ADMIN.name
)

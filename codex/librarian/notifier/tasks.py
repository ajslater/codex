"""Notifier Tasks."""
from dataclasses import dataclass

from codex.websockets.consumers import ChannelGroups


@dataclass
class NotifierTask:
    """Handle with the Notifier."""

    text: str
    type: ChannelGroups


LIBRARY_CHANGED_TASK = NotifierTask("LIBRARY_CHANGED", ChannelGroups.ALL)
LIBRARIAN_STATUS_TASK = NotifierTask("LIBRARIAN_STATUS", ChannelGroups.ADMIN)
FAILED_IMPORTS_TASK = NotifierTask("FAILED_IMPORTS", ChannelGroups.ADMIN)

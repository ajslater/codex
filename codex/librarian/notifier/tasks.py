"""Notifier Tasks."""
from dataclasses import dataclass

from codex.consumers.notifier import Channels


@dataclass
class NotifierTask:
    """Handle with the Notifier."""

    text: str
    type: Channels


LIBRARY_CHANGED_TASK = NotifierTask("LIBRARY_CHANGED", Channels.ALL)
LIBRARIAN_STATUS_TASK = NotifierTask("LIBRARIAN_STATUS", Channels.ADMIN)
FAILED_IMPORTS_TASK = NotifierTask("FAILED_IMPORTS", Channels.ADMIN)

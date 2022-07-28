"""Notifier Tasks."""
from dataclasses import dataclass
from enum import Enum


Channels = Enum("Channels", "ALL ADMIN")


@dataclass
class NotifierTask:
    """Handle with the Notifier."""

    type: Channels
    text: str


LIBRARY_CHANGED_TASK = NotifierTask(Channels.ALL, "LIBRARY_CHANGED")
LIBRARIAN_STATUS_TASK = NotifierTask(Channels.ADMIN, "LIBRARIAN_STATUS")
FAILED_IMPORTS_TASK = NotifierTask(Channels.ADMIN, "FAILED_IMPORTS")

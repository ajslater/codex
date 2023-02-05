"""Notifier Tasks."""
from dataclasses import dataclass
from enum import Enum
from typing import Callable


Channels = Enum("Channels", "ALL ADMIN")


@dataclass
class NotifierTask:
    """Handle with the Notifier."""

    text: str


@dataclass
class NotifierSendTask(NotifierTask):
    """Send text to these channels."""

    type: Channels


@dataclass
class NotifierSubscribeTask(NotifierTask):
    """Subscribe and Unsubscribe task."""

    subscribe: bool
    send: Callable


LIBRARY_CHANGED_TASK = NotifierSendTask("LIBRARY_CHANGED", Channels.ALL)
LIBRARIAN_STATUS_TASK = NotifierSendTask("LIBRARIAN_STATUS", Channels.ADMIN)
FAILED_IMPORTS_TASK = NotifierSendTask("FAILED_IMPORTS", Channels.ADMIN)

"""Notifier Tasks."""
from abc import ABC
from dataclasses import dataclass


@dataclass
class NotifierTask(ABC):
    """Handle with the Notifier."""

    text: str


@dataclass
class NotifierAdminTask(NotifierTask):
    """Notifications for admins only."""

    pass


@dataclass
class NotifierBroadcastTask(NotifierTask):
    """Notifications for all users."""

    pass

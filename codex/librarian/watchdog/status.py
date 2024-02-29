"""Watchdog Status Types."""

from django.db.models import Choices


class WatchdogStatusTypes(Choices):
    """Watchdog Status Types."""

    POLL = "WPO"

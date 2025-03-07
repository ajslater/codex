"""Watchdog Status Types."""

from django.db.models import TextChoices


class WatchdogStatusTypes(TextChoices):
    """Watchdog Status Types."""

    POLL = "WPO"

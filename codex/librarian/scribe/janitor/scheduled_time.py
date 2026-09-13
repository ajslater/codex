"""Janitor Scheduled time."""

from datetime import datetime, time, timedelta

from django.utils import timezone as django_timezone
from loguru._logger import Logger


def get_janitor_time(_log: Logger) -> datetime:
    """Get the next local midnight."""
    # Calendar arithmetic, not twenty four hours: on the night daylight
    # saving time ends the local day is 25 hours long, so adding a day to
    # the hour after midnight lands on the same date and hands back the
    # midnight that just went by.
    tomorrow = django_timezone.now().astimezone().date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min).astimezone()

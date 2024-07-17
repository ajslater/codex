"""Janitor Scheduled time."""

from datetime import datetime, time, timedelta

from django.utils import timezone as django_timezone


def get_janitor_time(_log):
    """Get midnight relative to now."""
    tomorrow = django_timezone.now() + timedelta(days=1)
    tomorrow = tomorrow.astimezone()
    return datetime.combine(tomorrow, time.min).astimezone()

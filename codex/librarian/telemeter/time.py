"""Get telemeter send time."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from codex.librarian.telemeter.telemeter import get_telemeter_timestamp
from codex.models.admin import AdminFlag

# Timing
_ONE_DAY = 24 * 60 * 60
_SECS_PER_WEEK = 7 * _ONE_DAY
_MAX_UUID = 2**128
_UUID_DIVISOR = _MAX_UUID / _SECS_PER_WEEK


def _get_utc_start_of_week():
    """Get timestamp for this Monady 00:00:00."""
    # Monday, now o'clock.
    utc_now = datetime.now(tz=timezone.utc)
    start_of_week = utc_now - timedelta(days=utc_now.weekday())
    # Monday, midnight.
    return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(
        tz=timezone.utc
    )


def _is_created_recently(ts):
    """Don't send if created recently."""
    now = datetime.now(tz=timezone.utc)
    since = ts.created_at - now
    return abs(since.total_seconds()) < _ONE_DAY


def _get_scheduled_time(ts):
    """Compute the time of week to send from the uuid."""
    start_of_week = _get_utc_start_of_week()
    uuid = UUID(ts.version)
    seconds_after_week_start = uuid.int / _UUID_DIVISOR
    time_of_week = timedelta(seconds=seconds_after_week_start)
    telemeter_time = start_of_week + time_of_week
    telemeter_time = telemeter_time.astimezone(tz=timezone.utc)
    if telemeter_time < ts.updated_at:
        # Already ran this week, or created this week after run time.
        telemeter_time = 0
    return telemeter_time


def get_telemeter_time(log):
    """Get the time to send telemetry."""
    # Should we schedule telemeter at all?
    if not AdminFlag.objects.get(key=AdminFlag.FlagChoices.SEND_TELEMETRY.value).on:
        log.debug("Telemeter disabled. Not scheduled.")
        return 0

    ts = get_telemeter_timestamp()

    if _is_created_recently(ts):
        log.debug("Telemeter created recently. Not scheduled.")
        return 0

    return _get_scheduled_time(ts)

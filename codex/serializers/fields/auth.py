"""Custom fields."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework.exceptions import ValidationError
from rest_framework.serializers import (
    CharField,
    IntegerField,
)

from codex.logger.logging import get_logger

LOG = get_logger(__name__)


class TimestampField(IntegerField):
    """IntegerTimestampField."""

    def to_representation(self, value) -> int:
        """Convert to Jascript millisecond int timestamp from datetime, or castable."""
        if isinstance(value, datetime):
            value = value.timestamp()
        return int(float(value) * 1000)

    def to_internal_value(self, data) -> datetime:  # type: ignore[reportIncompatibleMethodOverride]
        """Convert from castable, likely string to datetime."""
        return datetime.fromtimestamp(float(data) / 1000, tz=timezone.utc)


def validate_timezone(data):
    """Validate Timezone."""
    try:
        ZoneInfo(data)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError from exc
    return data


class TimezoneField(CharField):
    """Timezone field."""

    def __init__(self, *args, **kwargs):
        """Call Charfield with defaults."""
        super().__init__(*args, min_length=2, validators=[validate_timezone], **kwargs)

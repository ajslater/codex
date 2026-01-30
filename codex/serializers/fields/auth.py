"""Custom fields."""

from datetime import UTC, datetime
from typing import override
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework.exceptions import ValidationError
from rest_framework.serializers import (
    CharField,
    IntegerField,
)


class TimestampField(IntegerField):
    """IntegerTimestampField."""

    @override
    def to_representation(self, value) -> int:
        """Convert to Jascript millisecond int timestamp from datetime, or castable."""
        if isinstance(value, datetime):
            value = value.timestamp()
        return int(float(value) * 1000)

    @override
    def to_internal_value(self, data) -> datetime:  # pyright: ignore[reportIncompatibleMethodOverride], # ty: ignore[invalid-method-override]
        """Convert from castable, likely string to datetime."""
        return datetime.fromtimestamp(float(data) / 1000, tz=UTC)


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

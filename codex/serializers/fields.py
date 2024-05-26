"""Custom fields."""
from datetime import datetime

from rest_framework.fields import Field


class TimestampField(Field):
    """IntegerTimestampField."""

    def to_representation(self, value):
        """Convert to int from datetime, or castable."""
        if isinstance(value, datetime):
            return value.timestamp()
        return int(value)

    def to_internal_value(self, data):
        """Convert from castable, likely string."""
        return int(data)

"""Sanitied Fields."""

from nh3 import clean
from rest_framework.fields import CharField


class SanitizedCharField(CharField):
    """Sanitize CharField using NH3."""

    def to_internal_value(self, data):
        """Sanitize CharField using NH3."""
        sanitized_data = clean(data)
        return super().to_internal_value(sanitized_data)

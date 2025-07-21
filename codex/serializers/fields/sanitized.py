"""Sanitied Fields."""

from nh3 import clean
from rest_framework.fields import CharField
from typing_extensions import override


class SanitizedCharField(CharField):
    """Sanitize CharField using NH3."""

    @override
    def to_internal_value(self, data):
        """Sanitize CharField using NH3."""
        sanitized_data = clean(data)
        return super().to_internal_value(sanitized_data)

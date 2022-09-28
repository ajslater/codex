"""Custom url converters."""
from django.urls.converters import StringConverter


class GroupConverter(StringConverter):
    """Only accept valid browser groups."""

    regex = "[rpisvcf]"

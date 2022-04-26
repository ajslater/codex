"""Notification serializers."""
from rest_framework.serializers import BooleanField, Serializer


class NotifySerializer(Serializer):
    """Update notify flag."""

    update_in_progress = BooleanField(read_only=True)

"""Notification serializers."""
from rest_framework.serializers import BooleanField, Serializer


class NotifySerializer(Serializer):
    """Update notify flag."""

    updateInProgress = BooleanField(read_only=True)  # noqa: N815

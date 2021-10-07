"""Notification serializers."""
from rest_framework.serializers import BooleanField, Serializer


class ScanNotifySerializer(Serializer):
    """Scan notify flag."""

    scanInProgress = BooleanField(read_only=True)  # noqa: N815

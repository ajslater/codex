"""Notification serializers."""
from rest_framework.serializers import CharField, JSONField, Serializer

from codex.serializers.browser import BrowserSettingsSerializer


class ReaderRedirectSerializer(Serializer):
    """Reader 404 message."""

    reason = CharField(read_only=True)
    route = JSONField(read_only=True)


class BrowserRedirectSerializer(ReaderRedirectSerializer):
    """Redirect to another route."""

    settings = BrowserSettingsSerializer(read_only=True)

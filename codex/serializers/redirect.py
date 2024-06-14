"""Notification serializers."""

from rest_framework.serializers import CharField, Serializer

from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.serializers.route import RouteSerializer


class ReaderRedirectSerializer(Serializer):
    """Reader 404 message."""

    reason = CharField(read_only=True)
    route = RouteSerializer(read_only=True)


class BrowserRedirectSerializer(ReaderRedirectSerializer):
    """Redirect to another route."""

    settings = BrowserSettingsSerializer(read_only=True)

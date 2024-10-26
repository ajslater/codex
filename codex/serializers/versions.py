"""Versions Serializer."""

from rest_framework.serializers import Serializer

from codex.serializers.fields import SanitizedCharField


class VersionsSerializer(Serializer):
    """Codex version information."""

    installed = SanitizedCharField(read_only=True)
    latest = SanitizedCharField(read_only=True)

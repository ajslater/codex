"""Versions Serializer."""
from rest_framework.serializers import CharField, Serializer


class VersionsSerializer(Serializer):
    """Codex version information."""

    installed = CharField(read_only=True)
    latest = CharField(read_only=True)

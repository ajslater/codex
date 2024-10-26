"""Versions Serializer."""

from rest_framework.fields import CharField
from rest_framework.serializers import Serializer


class VersionsSerializer(Serializer):
    """Codex version information."""

    installed = CharField(read_only=True)
    latest = CharField(read_only=True)

"""Versions Serializer."""

from rest_framework.fields import BooleanField, CharField
from rest_framework.serializers import Serializer


class VersionsSerializer(Serializer):
    """Codex version information."""

    installed = CharField(read_only=True)
    latest = CharField(read_only=True)
    outdated = BooleanField(read_only=True)
    docker = BooleanField(read_only=True)
    warning = CharField(read_only=True)

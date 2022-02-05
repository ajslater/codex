"""Codex Serializers for the metadata box."""
from rest_framework.serializers import CharField

from codex.serializers.mixins import BrowserAggregateSerializerMixin
from codex.serializers.models import ComicSerializer


class MetadataSerializer(BrowserAggregateSerializerMixin, ComicSerializer):
    """Aggregate stats for the comics selected in the metadata dialog."""

    group = CharField(read_only=True)

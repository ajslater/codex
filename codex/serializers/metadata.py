"""Codex Serializers for the metadata box."""
from codex.serializers.mixins import (
    BrowserAggregateSerializerMixin,
    get_serializer_values_map,
)
from codex.serializers.models import ComicSerializer


METADATA_ORDERED_UNIONFIX_VALUES_MAP = get_serializer_values_map(
    [BrowserAggregateSerializerMixin], True
)


class MetadataSerializer(BrowserAggregateSerializerMixin, ComicSerializer):
    """Aggregate stats for the comics selected in the metadata dialog."""

    pass

"""Codex Serializers for the metadata box."""
from rest_framework.serializers import CharField, IntegerField

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

    filename = CharField(read_only=True)
    parent_folder_pk = IntegerField(read_only=True, required=False)

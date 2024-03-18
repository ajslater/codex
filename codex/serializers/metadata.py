"""Codex Serializers for the metadata box."""

from rest_framework.serializers import CharField, IntegerField

from codex.serializers.mixins import BrowserAggregateSerializerMixin
from codex.serializers.models.comic import ComicSerializer


class MetadataSerializer(BrowserAggregateSerializerMixin, ComicSerializer):
    """Aggregate stats for the comics selected in the metadata dialog."""

    filename = CharField(read_only=True)
    parent_folder_pk = IntegerField(read_only=True, required=False)
    series_volume_count = IntegerField(read_only=True)
    volume_issue_count = IntegerField(read_only=True)

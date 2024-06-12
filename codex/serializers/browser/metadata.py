"""Codex Serializers for the metadata box."""

from rest_framework.serializers import CharField, IntegerField, ListField, Serializer

from codex.serializers.browser.mixins import BrowserAggregateSerializerMixin
from codex.serializers.models.comic import ComicSerializer
from codex.serializers.models.named import (
    ContributorSerializer,
    IdentifierSeralizer,
    StoryArcNumberSerializer,
)

PREFETCH_PREFIX = "attached_"


class GroupSerializer(Serializer):
    """Serialize a group pk and name."""

    ids = ListField(child=IntegerField(), read_only=True)
    name = CharField(read_only=True)


class MetadataSerializer(BrowserAggregateSerializerMixin, ComicSerializer):
    """Aggregate stats for the comics selected in the metadata dialog."""

    filename = CharField(read_only=True)
    parent_folder_id = IntegerField(read_only=True, required=False)
    series_volume_count = IntegerField(read_only=True)
    volume_issue_count = IntegerField(read_only=True)

    publisher_list = GroupSerializer(many=True, required=False)
    imprint_list = GroupSerializer(many=True, required=False)
    series_list = GroupSerializer(many=True, required=False)
    volume_list = GroupSerializer(many=True, required=False)
    publisher = None
    imprint = None
    series = None
    volume = None

    identifiers = IdentifierSeralizer(
        source=f"{PREFETCH_PREFIX}identifiers", many=True, allow_null=True
    )
    contributors = ContributorSerializer(
        source=f"{PREFETCH_PREFIX}contributors", many=True, allow_null=True
    )
    stroy_arc_numbers = StoryArcNumberSerializer(
        source=f"{PREFETCH_PREFIX}story_arc_numbers", many=True, allow_null=True
    )

    class Meta(ComicSerializer.Meta):
        """Configure the model."""

        exclude = (
            *ComicSerializer.Meta.exclude,
            "publisher",
            "imprint",
            "series",
            "volume",
        )

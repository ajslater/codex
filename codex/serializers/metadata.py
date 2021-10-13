"""Codex Serializers for the metadata box."""

from rest_framework.serializers import (
    BooleanField,
    CharField,
    DecimalField,
    IntegerField,
    ListField,
    Serializer,
)

from codex.serializers.models import ComicSerializer


class MetadataAggregatesSerializer(Serializer):
    """Aggregate stats for the comics selected in the metadata dialog."""

    # Aggregate Annotations
    size = IntegerField(read_only=True)
    x_cover_path = CharField(read_only=True)
    x_page_count = IntegerField(read_only=True)

    # UserBookmark annotations
    bookmark = IntegerField(read_only=True)
    finished = BooleanField(read_only=True)
    progress = DecimalField(max_digits=5, decimal_places=2, read_only=True)


class MetadataSerializer(Serializer):
    """Data for the metadata dialog."""

    def __init__(self, *args, **kwargs):
        """Dynamically create comic field with 'fields' argument."""
        comic_fields = kwargs.get("comic_fields")
        self.fields["comic"] = ComicSerializer(fields=comic_fields)
        kwargs.pop("comic_fields")
        super().__init__(*args, **kwargs)

    # All the comic pks for a filtered aggregate group
    pks = ListField(child=IntegerField())

    # Aggregated stats for the group of comics selected.
    aggregates = MetadataAggregatesSerializer()

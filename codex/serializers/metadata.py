"""Codex Serializers for the metadata box."""

from rest_framework.serializers import BooleanField, DecimalField, IntegerField

from codex.serializers.mixins import UnionFixSerializerMixin
from codex.serializers.models import ComicSerializer


class MetadataSerializer(UnionFixSerializerMixin, ComicSerializer):
    """Aggregate stats for the comics selected in the metadata dialog."""

    # Aggregate Annotations
    child_count = IntegerField(read_only=True)

    # UserBookmark annotations
    bookmark = IntegerField(read_only=True)
    finished = BooleanField(read_only=True)
    progress = DecimalField(max_digits=5, decimal_places=2, read_only=True)

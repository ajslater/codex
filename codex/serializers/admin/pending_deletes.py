"""Pending delete serializers."""

from rest_framework.serializers import (
    CharField,
    DateTimeField,
    IntegerField,
    Serializer,
)


class PendingDeleteSerializer(Serializer):
    """
    One row the retention window is holding.

    Not a ModelSerializer: Comic and Folder are two models rendered into
    one list, and only the four shared columns matter here.
    """

    pk = IntegerField(read_only=True)
    collection = CharField(read_only=True)
    path = CharField(read_only=True)
    library_id = IntegerField(read_only=True)
    missing_since = DateTimeField(read_only=True)
    reap_after = DateTimeField(read_only=True)

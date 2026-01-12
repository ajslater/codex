"""OPDS 2.0 Metadata Serializer."""

from rest_framework.fields import CharField, DateTimeField, IntegerField
from rest_framework.serializers import Serializer


class OPDS2MetadataSerializer(Serializer):
    """
    Metadata.

    https://drafts.opds.io/schema/feed-metadata.schema.json
    """

    title = CharField(read_only=True)
    identifier = CharField(read_only=True, required=False)
    subtitle = CharField(read_only=True, required=False)
    modified = DateTimeField(read_only=True, required=False)
    description = CharField(read_only=True, required=False)
    items_per_page = IntegerField(read_only=True, required=False)
    current_page = IntegerField(read_only=True, required=False)
    number_of_items = IntegerField(read_only=True, required=False)

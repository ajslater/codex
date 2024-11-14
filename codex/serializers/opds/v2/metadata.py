"""OPDS 2.0 Metadata Serializer."""

from rest_framework.fields import CharField, DateTimeField
from rest_framework.serializers import Serializer


class OPDS2MetadataSerializer(Serializer):
    """
    Metadata.

    https://drafts.opds.io/schema/feed-metadata.schema.json
    """

    identifier = CharField(read_only=True, required=False)
    title = CharField(read_only=True)
    subtitle = CharField(read_only=True, required=False)
    modified = DateTimeField(read_only=True, required=False)
    description = CharField(read_only=True, required=False)

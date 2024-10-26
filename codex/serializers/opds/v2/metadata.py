"""OPDS 2.0 Metadata Serializer."""

from rest_framework.fields import DateTimeField
from rest_framework.serializers import Serializer

from codex.serializers.fields import SanitizedCharField


class OPDS2MetadataSerializer(Serializer):
    """
    Metadata.

    https://drafts.opds.io/schema/feed-metadata.schema.json
    """

    identifier = SanitizedCharField(read_only=True, required=False)
    title = SanitizedCharField(read_only=True)
    subtitle = SanitizedCharField(read_only=True, required=False)
    modified = DateTimeField(read_only=True, required=False)
    description = SanitizedCharField(read_only=True, required=False)

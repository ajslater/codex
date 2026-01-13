"""OPDS v2.0 Feed Serializer."""

from rest_framework.fields import (
    ListField,
)
from rest_framework.serializers import Serializer

from codex.serializers.opds.v2.facet import OPDS2FacetSerializer
from codex.serializers.opds.v2.links import OPDS2LinkListField
from codex.serializers.opds.v2.metadata import OPDS2MetadataSerializer
from codex.serializers.opds.v2.publication import OPDS2PublicationSerializer


class OPDS2GroupSerializer(Serializer):
    """
    Group.

    https://drafts.opds.io/opds-2.0.html#25-groups
    """

    metadata = OPDS2MetadataSerializer(read_only=True)
    links = OPDS2LinkListField(read_only=True, required=False)
    publications = ListField(
        child=OPDS2PublicationSerializer(), read_only=True, required=False
    )
    navigation = OPDS2LinkListField(read_only=True, required=False)


class OPDS2FeedSerializer(OPDS2GroupSerializer):
    """
    Feed.

    https://drafts.opds.io/schema/feed.schema.json
    https://readium.org/webpub-manifest/schema/subcollection.schema.json
    """

    facets = ListField(child=OPDS2FacetSerializer(), read_only=True, required=False)
    groups = ListField(child=OPDS2GroupSerializer(), read_only=True, required=False)

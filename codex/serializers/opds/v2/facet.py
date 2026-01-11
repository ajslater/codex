"""OPDS v2.0 Facet Serializer."""

from rest_framework.serializers import Serializer

from codex.serializers.opds.v2.links import OPDS2LinkListField
from codex.serializers.opds.v2.metadata import OPDS2MetadataSerializer


class OPDS2FacetSerializer(Serializer):
    """
    Facets.

    https://drafts.opds.io/opds-2.0.html#24-facets
    """

    metadata = OPDS2MetadataSerializer(read_only=True)
    links = OPDS2LinkListField(read_only=True)

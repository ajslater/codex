"""OPDS v2.0 Links Serializers."""

from rest_framework.fields import (
    BooleanField,
    CharField,
    IntegerField,
    ListField,
    SerializerMethodField,
)
from rest_framework.serializers import Serializer


class OPSD2AuthenticateSerializer(Serializer):
    """Minimal Link Serializer for Authenticate."""

    href = CharField(read_only=True)
    rel = SerializerMethodField(read_only=True)
    type = CharField(read_only=True, required=False)

    def get_rel(self, obj) -> str | None:
        """Allow for SanitizedCharField or CharListField types."""
        rel = obj.get("rel")
        if not isinstance(rel, list | str):
            reason = "OPDS2LinkSerializer.rel is not a list or a string."
            raise TypeError(reason)
        return obj.get("rel")


class OPDS2LinkPropertiesSerializer(Serializer):
    """
    Link Properties.

    https://drafts.opds.io/schema/properties.schema.json
    """

    number_of_items = IntegerField(read_only=True, required=False)
    # price = OPDS2PriceSerializer(read_only=True, required=False) unused
    # indirect_aquisition = OPDS2AcquisitionObjectSerializer( unused
    #    read_only=True, many=True, required=False unused
    # ) unused
    # holds = OPDS2HoldsSerializer(read_only=True, required=False) unused
    # copies = OPDS2CopiesSerializer(read_only=True, required=False) unused
    # availability = OPDS2AvailabilitySerializer(read_only=True, required=False) unused
    authenticate = OPSD2AuthenticateSerializer(required=False)


class OPDS2LinkSerializer(OPSD2AuthenticateSerializer):
    """
    Link.

    https://readium.org/webpub-manifest/schema/link.schema.json
    """

    templated = BooleanField(read_only=True, required=False)
    title = CharField(read_only=True, required=False)

    # Uncommon
    height = IntegerField(read_only=True, required=False)
    width = IntegerField(read_only=True, required=False)
    # bitrate = IntegerField(read_only=True, required=False) unused
    # duration = IntegerField(read_only=True, required=False) unused
    # language = CharField(many=True, read_only=True, required=False) unused
    alternate = ListField(
        child=CharField(read_only=True), read_only=True, required=False
    )
    children = ListField(
        child=CharField(read_only=True), read_only=True, required=False
    )
    properties = OPDS2LinkPropertiesSerializer(read_only=True, required=False)


class OPDS2LinkListField(ListField):
    """Link List."""

    child = OPDS2LinkSerializer()

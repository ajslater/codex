"""OPDS v2.0 Links Serializers."""

from rest_framework.fields import (
    BooleanField,
    CharField,
    IntegerField,
    ListField,
    SerializerMethodField,
)
from rest_framework.serializers import Serializer
from typing_extensions import override


class OPSD2AuthenticateSerializer(Serializer):
    """Minimal Link Serializer for Authenticate."""

    href = CharField(read_only=True)
    rel = SerializerMethodField(read_only=True, required=False)
    type = CharField(read_only=True, required=False)

    def get_rel(self, obj) -> str | list[str] | None:
        """Allow for SanitizedCharField or CharListField types."""
        rel: str | list[str] | None = obj.get("rel")
        if rel and not isinstance(rel, list | str):
            reason = "OPDS2LinkSerializer.rel is not a list or a string."
            raise TypeError(reason)
        return rel

    @override
    def to_representation(self, instance):  # ty: ignore[invalid-method-override]
        """Clean complex rel field if None."""
        ret = super().to_representation(instance)

        if "rel" in ret and not ret["rel"]:
            del ret["rel"]

        return ret


class OPDS2LinkPropertiesSerializer(Serializer):
    """
    Link Properties.

    https://drafts.opds.io/schema/properties.schema.json
    """

    number_of_items = IntegerField(read_only=True, required=False)
    # price = OPDS2PriceSerializer(read_only=True, required=False) unused
    # indirect_acquisition = OPDS2AcquisitionObjectSerializer( unused
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
    properties = OPDS2LinkPropertiesSerializer(read_only=True, required=False)

    # Images
    height = IntegerField(read_only=True, required=False)
    width = IntegerField(read_only=True, required=False)

    # Uncommon
    # bitrate = IntegerField(read_only=True, required=False) unused
    # duration = IntegerField(read_only=True, required=False) unused
    # language = CharField(many=True, read_only=True, required=False) unused
    alternate = ListField(
        child=CharField(read_only=True), read_only=True, required=False
    )
    children = ListField(
        child=CharField(read_only=True), read_only=True, required=False
    )


class OPDS2LinkListField(ListField):
    """Link List."""

    child = OPDS2LinkSerializer()

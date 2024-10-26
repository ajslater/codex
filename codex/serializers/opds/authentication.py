"""
OPDS Authentication 1.0 Serializer.

https://drafts.opds.io/schema/authentication.schema.json
"""

from rest_framework.serializers import IntegerField, Serializer

from codex.serializers.fields import SanitizedCharField


class OPDSAuth1LinksSerializer(Serializer):
    """OPDS Authentication Links."""

    rel = SanitizedCharField(read_only=True)
    href = SanitizedCharField(read_only=True)
    type = SanitizedCharField(read_only=True)
    width = IntegerField(read_only=True, required=False)
    height = IntegerField(read_only=True, required=False)


class OPDSAuthetication1LabelsSerializer(Serializer):
    """Authentication Labels."""

    login = SanitizedCharField(read_only=True)
    password = SanitizedCharField(read_only=True)


class OPDSAuthentication1FlowSerializer(Serializer):
    """Authentication Flow."""

    type = SanitizedCharField(read_only=True)
    links = OPDSAuth1LinksSerializer(many=True, read_only=True, required=False)
    labels = OPDSAuthetication1LabelsSerializer(read_only=True)


class OPDSAuthentication1Serializer(Serializer):
    """Authentication."""

    title = SanitizedCharField(read_only=True)
    id = SanitizedCharField(read_only=True)
    description = SanitizedCharField(required=False, read_only=True)
    links = OPDSAuth1LinksSerializer(many=True, read_only=True, required=False)
    authentication = OPDSAuthentication1FlowSerializer(many=True, read_only=True)

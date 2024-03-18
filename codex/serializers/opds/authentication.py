"""OPDS Authentication 1.0 Serializer.

https://drafts.opds.io/schema/authentication.schema.json
"""

from rest_framework.serializers import CharField, IntegerField, Serializer


class OPDSAuth1LinksSerializer(Serializer):
    """OPDS Authentication Links."""

    rel = CharField(read_only=True)
    href = CharField(read_only=True)
    type = CharField(read_only=True)
    width = IntegerField(read_only=True, required=False)
    height = IntegerField(read_only=True, required=False)


class OPDSAuthetication1LabelsSerializer(Serializer):
    """Authentication Labels."""

    login = CharField(read_only=True)
    password = CharField(read_only=True)


class OPDSAuthentication1FlowSerializer(Serializer):
    """Authentication Flow."""

    type = CharField(read_only=True)
    links = OPDSAuth1LinksSerializer(many=True, read_only=True, required=False)
    labels = OPDSAuthetication1LabelsSerializer(read_only=True)


class OPDSAuthentication1Serializer(Serializer):
    """Authentication."""

    title = CharField(read_only=True)
    id = CharField(read_only=True)
    description = CharField(required=False, read_only=True)
    links = OPDSAuth1LinksSerializer(many=True, read_only=True, required=False)
    authentication = OPDSAuthentication1FlowSerializer(many=True, read_only=True)

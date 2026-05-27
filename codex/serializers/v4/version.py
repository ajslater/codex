"""v4 version serializer."""

from rest_framework.fields import CharField
from rest_framework.serializers import Serializer


class VersionEnvelopeSerializer(Serializer):
    """Version info delivered inside the v4 envelope ``data`` slot."""

    installed = CharField(read_only=True)
    latest = CharField(read_only=True)
    warning = CharField(read_only=True)

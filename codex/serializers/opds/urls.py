"""OPDS URLs."""

from rest_framework.fields import CharField
from rest_framework.serializers import Serializer


class OPDSURLsSerializer(Serializer):
    """OPDS Urls."""

    v1 = CharField(read_only=True)
    v2 = CharField(read_only=True)

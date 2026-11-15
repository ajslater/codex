"""API URLs."""

from rest_framework.fields import CharField
from rest_framework.serializers import Serializer


class ApiUrlsSerializer(Serializer):
    """The paths of the APIs this visitor may use. A missing one is off."""

    opds_v1 = CharField(read_only=True, required=False)
    opds_v2 = CharField(read_only=True, required=False)
    koreader = CharField(read_only=True, required=False)
    stats = CharField(read_only=True, required=False)

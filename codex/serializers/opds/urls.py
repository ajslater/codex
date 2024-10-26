"""OPDS URLs."""

from rest_framework.serializers import Serializer

from codex.serializers.fields import SanitizedCharField


class OPDSURLsSerializer(Serializer):
    """OPDS Urls."""

    v1 = SanitizedCharField(read_only=True)
    v2 = SanitizedCharField(read_only=True)

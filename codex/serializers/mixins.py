"""Serializer mixins."""

from rest_framework.serializers import (
    BooleanField,
    Serializer,
)


class OKSerializer(Serializer):
    """Default serializer for views without much response."""

    ok = BooleanField(default=True)

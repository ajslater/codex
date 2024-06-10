"""Settings Serializer."""

from rest_framework.fields import CharField
from rest_framework.serializers import ListSerializer, Serializer


class SettingsSerializer(Serializer):
    """For requesting settings."""

    only = ListSerializer(child=CharField(), required=False)
    group = CharField(required=False)

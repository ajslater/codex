"""Settings Serializer."""

from rest_framework.fields import BooleanField, CharField
from rest_framework.serializers import ListSerializer, Serializer


class SettingsSerializer(Serializer):
    """For requesting settings."""

    only = ListSerializer(child=CharField(), required=False)
    group = CharField(required=False)
    breadcrumb_names = BooleanField(required=False, default=True)

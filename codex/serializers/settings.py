"""Settings Serializer."""

from rest_framework.fields import BooleanField
from rest_framework.serializers import ListSerializer, Serializer

from codex.serializers.fields import BrowseGroupField, SessionKeyField


class SettingsSerializer(Serializer):
    """For requesting settings."""

    only = ListSerializer(child=SessionKeyField(), required=False)
    group = BrowseGroupField(required=False)
    breadcrumb_names = BooleanField(required=False, default=True)

"""Settings Serializer."""

from rest_framework.serializers import ListSerializer, Serializer

from codex.serializers.fields import SessionKeyField


class SettingsInputSerializer(Serializer):
    """For requesting settings."""

    JSON_PARAMS = frozenset({"only"})

    only = ListSerializer(child=SessionKeyField(), required=False)

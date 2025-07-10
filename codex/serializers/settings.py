"""Settings Serializer."""

from rest_framework.serializers import ListSerializer

from codex.serializers.fields import SessionKeyField
from codex.serializers.mixins import JSONFieldSerializer

from codex.serializers.fields import BrowseGroupField, SessionKeyField


class SettingsInputSerializer(JSONFieldSerializer):
    """For requesting settings."""

    JSON_PARAMS = frozenset({"only"})

    only = ListSerializer(child=SessionKeyField(), required=False)

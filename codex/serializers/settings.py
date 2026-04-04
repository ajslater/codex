"""Settings Serializer."""

from rest_framework.serializers import ListSerializer

from codex.serializers.fields.settings import SettingsKeyField
from codex.serializers.mixins import JSONFieldSerializer


class SettingsInputSerializer(JSONFieldSerializer):
    """For requesting settings."""

    JSON_PARAMS = frozenset({"only"})

    only = ListSerializer(child=SettingsKeyField(), required=False)

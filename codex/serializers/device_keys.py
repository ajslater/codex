"""Device key serializers."""

from rest_framework.fields import CharField
from rest_framework.serializers import Serializer

from codex.models.api_key import DEVICE_KEY_NAME_MAX_LENGTH


class DeviceKeyNameSerializer(Serializer):
    """Input for creating or renaming a device key."""

    name = CharField(max_length=DEVICE_KEY_NAME_MAX_LENGTH, trim_whitespace=True)

"""API key serializers."""

from rest_framework.exceptions import ValidationError
from rest_framework.fields import CharField, ChoiceField
from rest_framework.serializers import Serializer

from codex.choices.api_key import UNIVERSAL_KEY_NAME, ApiKeyScope
from codex.choices.limits import API_KEY_NAME_MAX_LENGTH


class ApiKeyNameSerializer(Serializer):
    """Input for renaming an API key."""

    name = CharField(max_length=API_KEY_NAME_MAX_LENGTH, trim_whitespace=True)

    def validate_name(self, value: str) -> str:
        """Keep the migrated bearer tokens' name for them alone."""
        if value == UNIVERSAL_KEY_NAME:
            reason = f"{UNIVERSAL_KEY_NAME} is a reserved name."
            raise ValidationError(reason)
        return value


class ApiKeyCreateSerializer(ApiKeyNameSerializer):
    """Input for creating an API key."""

    scope = ChoiceField(choices=ApiKeyScope.choices, default=ApiKeyScope.DEVICE)

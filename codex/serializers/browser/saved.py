"""Serializers for saved browser settings."""

from rest_framework.fields import BooleanField, CharField, IntegerField
from rest_framework.serializers import ListSerializer, Serializer

from codex.serializers.browser.settings import BrowserSettingsSerializer


class SavedSettingNameSerializer(Serializer):
    """A single saved setting entry."""

    pk = IntegerField(read_only=True)
    name = CharField(read_only=True)


class SavedBrowserSettingsListSerializer(Serializer):
    """List of saved browser settings."""

    saved_settings = SavedSettingNameSerializer(
        many=True,
        read_only=True,
        source="savedSettings",
    )


class SavedBrowserSettingsSaveSerializer(Serializer):
    """Input for saving browser settings with a name."""

    name = CharField(max_length=32, required=True)
    # Output-only fields
    created = BooleanField(read_only=True)


class SavedSettingsLoadSerializer(Serializer):
    """Response for loading a saved setting."""

    settings = BrowserSettingsSerializer(read_only=True)
    filter_warnings = ListSerializer(
        child=CharField(),
        read_only=True,
        source="filterWarnings",
    )

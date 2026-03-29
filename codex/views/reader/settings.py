"""Reader session view."""

from types import MappingProxyType

from rest_framework.serializers import BaseSerializer

from codex.models.settings import ClientChoices, SettingsReader
from codex.serializers.reader import ReaderSettingsSerializer
from codex.views.settings.base import SettingsReadView, SettingsWriteView
from codex.views.settings.settings import SettingsView


class ReaderSettingsReadView(SettingsReadView):
    """Reader settings configuration (read-only)."""

    MODEL = SettingsReader
    CLIENT = ClientChoices.API
    FILTER_ARGS = MappingProxyType(
        {
            "comic__isnull": True,
            "series__isnull": True,
            "folder__isnull": True,
        }
    )


class ReaderSettingsView(ReaderSettingsReadView, SettingsView):
    """Get and update global reader settings."""

    serializer_class: type[BaseSerializer] | None = ReaderSettingsSerializer
    REJECT_NULL_UPDATES = True


class ReaderSettingsWriteView(ReaderSettingsReadView, SettingsWriteView):
    """Reader settings with full mutation support."""

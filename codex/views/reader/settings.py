"""Reader session view."""

from rest_framework.serializers import BaseSerializer

from codex.serializers.reader import ReaderSettingsSerializer
from codex.views.settings import SettingsView


class ReaderSettingsView(SettingsView):
    """Get Reader Settings."""

    serializer_class: type[BaseSerializer] | None = ReaderSettingsSerializer

    SESSION_KEY: str = "reader"

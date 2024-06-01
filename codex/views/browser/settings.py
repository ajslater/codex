"""Browser session view."""

from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.views.settings import SettingsView


class BrowserSettingsView(SettingsView):
    """Get Browser Settings."""

    # Put Browser Settings is normally done through BrowserView.get()
    serializer_class = BrowserSettingsSerializer  # type: ignore

    SESSION_KEY = SettingsView.BROWSER_SESSION_KEY

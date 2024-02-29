"""Browser session view."""

from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.views.session import BrowserSessionViewBase, SessionViewBase


class BrowserSessionView(BrowserSessionViewBase, SessionViewBase):
    """Get Browser Settings."""

    # Put Browser Settings is normally done through BrowserView.get()

    serializer_class = BrowserSettingsSerializer  # type: ignore

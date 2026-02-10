"""OPDS Browser View."""

from codex.views.browser.browser import BrowserView
from codex.views.mixins import UserActiveMixin
from codex.views.opds.session import OPDSBrowserSessionMixin


class OPDSBrowserView(OPDSBrowserSessionMixin, UserActiveMixin, BrowserView):
    """OPDS Browser View."""

    def __init__(self, *args, **kwargs):
        """Add User Agent Name."""
        super().__init__(*args, **kwargs)
        self._user_agent_name: str | None = None  # pyright: ignore[reportIncompatibleUnannotatedOverride]

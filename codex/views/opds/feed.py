"""OPDS Browser View."""

from codex.views.browser.browser import BrowserView
from codex.views.mixins import UserActiveMixin
from codex.views.opds.session import OPDSBrowserSessionMixin
from codex.views.opds.util import get_user_agent_name


class OPDSBrowserView(OPDSBrowserSessionMixin, UserActiveMixin, BrowserView):
    """OPDS Browser View."""

    def __init__(self, *args, **kwargs):
        """Add User Agent Name."""
        super().__init__(*args, **kwargs)
        self._user_agent_name: str | None = None

    @property
    def user_agent_name(self) -> str:
        """Memoize user agent name."""
        if self._user_agent_name is None:
            self._user_agent_name = get_user_agent_name(self.request)
        return self._user_agent_name

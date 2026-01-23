"""OPDS Browser View."""

from codex.views.browser.browser import BrowserView
from codex.views.mixins import UserActiveMixin
from codex.views.opds.session import OPDSBrowserSessionMixin


class OPDSBrowserView(OPDSBrowserSessionMixin, UserActiveMixin, BrowserView):
    """OPDS Browser View."""

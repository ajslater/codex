"""OPDS Browser View."""

from types import MappingProxyType

from codex.views.browser.browser import BrowserView
from codex.views.opds.auth import OPDSAuthMixin


class OPDSViewMixin(OPDSAuthMixin):
    """OPDS View isolates OPDS sessions data."""

    BROWSER_SESSION_KEY = "opds_browser"
    READER_SESSION_KEY = "opds_reader"
    SESSION_KEY = BROWSER_SESSION_KEY
    SESSION_DEFAULTS = MappingProxyType(
        {
            BROWSER_SESSION_KEY: BrowserView.SESSION_DEFAULTS[
                BrowserView.BROWSER_SESSION_KEY
            ],
            READER_SESSION_KEY: BrowserView.SESSION_DEFAULTS[
                BrowserView.READER_SESSION_KEY
            ],
        }
    )


class OPDSBrowserView(OPDSViewMixin, BrowserView):
    """OPDS Browser View."""

    SESSION_KEY = OPDSViewMixin.BROWSER_SESSION_KEY

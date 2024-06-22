"""Binary views with Basic Authentication added."""

from codex.views.browser.cover import CoverView
from codex.views.download import DownloadView
from codex.views.opds.auth import OPDSAuthMixin
from codex.views.reader.page import ReaderPageView


class OPDSCoverView(OPDSAuthMixin, CoverView):
    """Cover View with Basic Auth."""


class OPDSDownloadView(OPDSAuthMixin, DownloadView):
    """Download View with Basic Auth."""


class OPDSPageView(OPDSAuthMixin, ReaderPageView):
    """Page View with Basic Auth."""

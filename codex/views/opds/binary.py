"""Binary views with Basic Authentication added."""

from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from codex.views.cover import CoverView
from codex.views.download import DownloadView
from codex.views.reader.page import ReaderPageView


class OPDSAuthMixin:
    """Add Basic Auth."""

    authentication_classes = (BasicAuthentication, SessionAuthentication)


class OPDSCoverView(OPDSAuthMixin, CoverView):
    """Cover View with Basic Auth."""


class OPDSDownloadView(OPDSAuthMixin, DownloadView):
    """Download View with Basic Auth."""


class OPDSPageView(OPDSAuthMixin, ReaderPageView):
    """Page View with Basic Auth."""

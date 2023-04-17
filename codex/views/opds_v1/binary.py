"""Binary views with Basic Authentication added."""
from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from codex.views.cover import CoverView
from codex.views.download import DownloadView
from codex.views.reader.page import ReaderPageView


class OPDS1AuthMixin:
    """Add Basic Auth."""

    authentication_classes = (BasicAuthentication, SessionAuthentication)


class OPDS1CoverView(OPDS1AuthMixin, CoverView):
    """Cover View with Basic Auth."""


class OPDS1DownloadView(OPDS1AuthMixin, DownloadView):
    """Download View with Basic Auth."""


class OPDS1PageView(OPDS1AuthMixin, ReaderPageView):
    """Page View with Basic Auth."""

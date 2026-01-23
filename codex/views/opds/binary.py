"""Binary views with Basic Authentication added."""

from rest_framework.negotiation import BaseContentNegotiation
from typing_extensions import override

from codex.views.browser.cover import CoverView
from codex.views.download import DownloadView
from codex.views.opds.auth import OPDSAuthMixin
from codex.views.opds.session import OPDSBrowserSessionMixin
from codex.views.reader.page import ReaderPageView


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    """Hack for clients with wild accept headers."""

    @override
    def select_parser(self, request, parsers):
        """Select the first parser in the `.parser_classes` list."""
        return next(iter(parsers))

    @override
    def select_renderer(
        self,
        request,
        renderers,
        format_suffix="",
    ):
        """Select the first renderer in the `.renderer_classes` list."""
        renderer = next(iter(renderers))
        return (renderer, renderer.media_type)


class OPDSCoverView(OPDSBrowserSessionMixin, CoverView):
    """Cover View with Basic Auth."""


class OPDSDownloadView(OPDSAuthMixin, DownloadView):
    """Download View with Basic Auth."""


class OPDSPageView(OPDSAuthMixin, ReaderPageView):
    """Page View with Basic Auth."""

    content_negotiation_class: type[BaseContentNegotiation] = (  # pyright:ignore[reportIncompatibleVariableOverride]
        IgnoreClientContentNegotiation
    )

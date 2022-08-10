"""Serve an opensearch document."""
from django.views.generic import TemplateView

from codex.settings.logging import get_logger
from codex.views.opds_v1.mixins import OPDSAuthenticationMixin


LOG = get_logger(__name__)


class OpenSearchView(TemplateView, OPDSAuthenticationMixin):
    """OpenSearchView."""

    template_name = "opds/opensearch.xml"
    content_type = "application/xml"

    def get(self, request, *args, **kwargs):
        """Authenticate the search document.."""
        response = self._authenticate(request)
        if response:
            return response
        return super().get(request, *args, **kwargs)

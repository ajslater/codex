"""Serve an opensearch document."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.template import CodexXMLTemplateView


@extend_schema(responses={("200", "application/xml"): OpenApiTypes.BYTE})
class OpenSearchView(CodexXMLTemplateView):
    """OpenSearchView."""

    authentication_classes = (SessionAuthentication, BasicAuthentication)
    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
    template_name = "opds/opensearch.xml"
    content_type = "application/xml"

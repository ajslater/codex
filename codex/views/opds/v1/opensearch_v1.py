"""Serve an opensearch v1 document."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.template import CodexXMLTemplateView


@extend_schema(responses={("200", "application/xml"): OpenApiTypes.BYTE})
class OpenSearch1View(CodexXMLTemplateView):
    """OpenSearchView."""

    authentication_classes = (BasicAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticatedOrEnabledNonUsers,)
    template_name = "opds_v1/opensearch_v1.xml"
    content_type = "application/xml"

"""Serve an opensearch v1 document."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.throttling import ScopedRateThrottle

from codex.views.opds.auth import OPDSTemplateView


@extend_schema(responses={("200", "application/xml"): OpenApiTypes.BYTE})
class OpenSearch1View(OPDSTemplateView):
    """OpenSearchView."""

    template_name = "opds_v1/opensearch_v1.xml"
    content_type = "application/xml"
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "opensearch"

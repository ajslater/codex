"""Serve an opensearch v1 document."""

from collections.abc import Sequence

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.throttling import BaseThrottle, ScopedRateThrottle

from codex.views.opds.auth import OPDSTemplateMixin
from codex.views.template import CodexAPIView


@extend_schema(responses={("200", "application/xml"): OpenApiTypes.BYTE})
class OpenSearch1View(OPDSTemplateMixin, CodexAPIView):
    """OpenSearchView."""

    template_name = "opds_v1/opensearch_v1.xml"
    content_type = "application/xml"
    throttle_classes: Sequence[type[BaseThrottle]] = (ScopedRateThrottle,)
    throttle_scope = "opensearch"

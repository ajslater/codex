"""Serve an opensearch v1 document."""

from collections.abc import Sequence

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.renderers import BaseRenderer
from rest_framework.throttling import BaseThrottle

from codex.throttling import ScopedRateThrottle
from codex.views.opds.auth import OPDSAuthMixin
from codex.views.opds.const import MimeType
from codex.views.template import (
    CodexAPIView,
    CodexXMLTemplateMixin,
    TemplateXMLRenderer,
)


class OpenSearchRenderer(TemplateXMLRenderer):
    """Render the OpenSearch description with its official media type."""

    media_type = MimeType.OPENSEARCH
    format = "opensearch"


class _OpenSearchTemplateMixin(CodexXMLTemplateMixin):
    """
    XML template mixin that serves the OpenSearch media type.

    The OpenSearch spec defines the media type for description documents as
    ``application/opensearchdescription+xml`` (which the OPDS feed's search link
    already advertises), so the document is served and content-negotiated under
    that type rather than the generic ``application/xml``.
    """

    content_type = MimeType.OPENSEARCH
    renderer_classes: Sequence[type[BaseRenderer]] = (OpenSearchRenderer,)


@extend_schema(responses={("200", MimeType.OPENSEARCH): OpenApiTypes.BYTE})
class OpenSearch1View(_OpenSearchTemplateMixin, OPDSAuthMixin, CodexAPIView):  # pyright: ignore[reportIncompatibleVariableOverride]
    """OpenSearchView."""

    # ``_OpenSearchTemplateMixin`` must precede ``OPDSAuthMixin`` so its
    # OpenSearch XML renderer wins MRO resolution — otherwise the auth mixin's
    # envelope renderer takes over and the endpoint returns ``{"data":{},...}``
    # instead of the XML description document.
    template_name = "opds_v1/opensearch_v1.xml"
    throttle_classes: Sequence[type[BaseThrottle]] = (ScopedRateThrottle,)
    throttle_scope = "opensearch"

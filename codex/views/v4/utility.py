"""
API v4 utility endpoints: OPDS URLs, covers, schema.

* ``GET /api/v4/opds-urls`` — wraps the v3 OPDSURLsView in the envelope.
* ``GET /api/v4/covers/{source}/{id}`` — generalized cover-by-source
  endpoint. v3 served ``c/<pk>/cover.webp`` and ``custom_cover/<pk>/
  cover.webp`` as separate routes; v4 merges them behind a ``source``
  segment (``comic`` | ``custom`` today; ``publisher`` / ``series`` /
  etc. are deferred until v3's group → representative-comic resolver
  is wrapped). Unknown sources 404 without leaking shape.
* ``GET /api/v4/schema`` — drf-spectacular schema view.
"""

from django.http import HttpResponse
from drf_spectacular.views import SpectacularAPIView

from codex.views.browser.cover import CoverView, CustomCoverView
from codex.views.opds.urls import OPDSURLsView
from codex.views.v4.common import EnvelopeJSONRenderer

_COVER_VIEW_BY_SOURCE = {
    "comic": CoverView,
    "custom": CustomCoverView,
}


class V4OPDSURLsView(OPDSURLsView):
    """``GET /api/v4/opds-urls``."""

    renderer_classes = (EnvelopeJSONRenderer,)


class V4SchemaView(SpectacularAPIView):
    """
    ``GET /api/v4/schema`` — OpenAPI 3 schema.

    Inherits drf-spectacular's renderer chain (YAML + JSON) so the
    envelope renderer is intentionally *not* layered on; clients of
    ``/schema`` expect the raw OpenAPI document.
    """


def v4_cover_dispatch(request, source: str, pk: int) -> HttpResponse:
    """Route ``/api/v4/covers/{source}/{id}`` to the matching v3 cover view."""
    view_cls = _COVER_VIEW_BY_SOURCE.get(source)
    if view_cls is None:
        return HttpResponse(status=404)
    view = view_cls.as_view()
    return view(request, pk=pk)

"""
API v4 utility endpoints: OPDS URLs, covers, schema.

* ``GET /api/v4/opds-urls`` — wraps the v3 OPDSURLsView in the envelope.
* ``GET /api/v4/covers/{source}/{id}`` — cover by source kind. ``source``
  is one of ``comic`` | ``custom`` | ``publisher`` | ``imprint`` |
  ``series`` | ``volume`` | ``folder`` | ``arc``. Non-comic sources
  resolve a representative comic pk (cheapest stable pick: ACL-filtered
  ``order_by('sort_name', 'pk').first()``) and delegate to ``CoverView``
  so caching, 202-then-poll, and missing-cover fallback all behave the
  same as the comic case. Unknown sources 404 without leaking shape.
* ``GET /api/v4/schema`` — drf-spectacular schema view.
"""

from typing import Final

from django.http import HttpResponse
from drf_spectacular.views import SpectacularAPIView

from codex.models import Comic
from codex.views.auth import GroupACLMixin
from codex.views.browser.cover import CoverView, CustomCoverView
from codex.views.browser.mtime import MtimeView
from codex.views.opds.urls import OPDSURLsView
from codex.views.v4.common import EnvelopeJSONRenderer

# source → (queryset filter kwargs builder) for representative-comic
# resolution. Keys mirror the v4 ``collection`` vocabulary but use the
# singular noun the URL emits. ``comic`` and ``custom`` are handled
# directly by the v3 cover views and never enter this map.
_GROUP_COMIC_FILTER: Final = {
    "publisher": "publisher_id",
    "imprint": "imprint_id",
    "series": "series_id",
    "volume": "volume_id",
    "folder": "folders",
    "arc": "story_arc_numbers__story_arc_id",
}


class V4OPDSURLsView(OPDSURLsView):
    """``GET /api/v4/opds-urls``."""

    renderer_classes = (EnvelopeJSONRenderer,)


class V4MtimeView(MtimeView):
    """``GET /api/v4/mtime`` — interim until typed WS payloads carry mtime+scope.

    The v4 plan removes ``/mtime`` in favor of mtime+scope on the
    push side (typed WS messages). That broadcaster enrichment is a
    separate body change; this endpoint exists so the migrated
    browser/reader stores can keep their ``loadMtimes()`` cache
    validation working through the cutover. Remove once broadcasters
    carry mtime/scope natively.
    """

    renderer_classes = (EnvelopeJSONRenderer,)


class V4SchemaView(SpectacularAPIView):
    """
    ``GET /api/v4/schema`` — OpenAPI 3 schema.

    Inherits drf-spectacular's renderer chain (YAML + JSON) so the
    envelope renderer is intentionally *not* layered on; clients of
    ``/schema`` expect the raw OpenAPI document.
    """


def _resolve_group_comic_pk(source: str, pk: int, user) -> int | None:
    """Pick a representative comic pk for a group source, ACL-aware."""
    field = _GROUP_COMIC_FILTER.get(source)
    if field is None:
        return None
    acl_q = GroupACLMixin.get_group_acl_filter(Comic, user)
    age_q = GroupACLMixin.get_age_rating_acl_filter(Comic, user)
    return (
        Comic.objects.filter(acl_q & age_q, **{field: pk})
        .order_by("sort_name", "pk")
        .values_list("pk", flat=True)
        .first()
    )


def _missing_cover_404() -> HttpResponse:
    """Return the same 404+no-store body CoverView emits when nothing matches."""
    resp = HttpResponse(b"", content_type="image/webp", status=404)
    resp["Cache-Control"] = "no-store"
    return resp


def v4_cover_dispatch(request, source: str, pk: int) -> HttpResponse:
    """Route ``/api/v4/covers/{source}/{id}`` by source kind."""
    if source == "comic":
        return CoverView.as_view()(request, pk=pk)
    if source == "custom":
        return CustomCoverView.as_view()(request, pk=pk)
    comic_pk = _resolve_group_comic_pk(source, pk, request.user)
    if comic_pk is None:
        return _missing_cover_404()
    return CoverView.as_view()(request, pk=comic_pk)

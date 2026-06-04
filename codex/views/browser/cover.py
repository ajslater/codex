"""
Per-pk cover endpoints.

Serve a single already-resolved cover pk — no group filter, no ordering,
no fuzzy sort_name matching. The browser response pre-computes the
representative comic pk per card (see :mod:`codex.views.browser.annotate.cover`),
so the per-card cover URL is a cheap single-row lookup instead of re-running
the group-resolution pipeline 72x per page.

Cover generation is never run inline. If the cached thumb is missing we
enqueue a :class:`CoverCreateTask` on the librarian queue and respond 202
Accepted with ``Retry-After`` so the client has something to render while
the cover thread produces the real bytes. When a cover can't be produced
(or doesn't exist) we respond 404 with an empty body — the web client
falls back to its ``lazy-src`` SVG and OPDS clients use their own default
rendering.
"""

from collections.abc import Sequence
from typing import Any, Final, override

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from loguru import logger
from rest_framework import status
from rest_framework.renderers import BaseRenderer

from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.covers.tasks import CoverCreateTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models import Comic
from codex.views.auth import AuthFilterAPIView, GroupACLMixin

# source → queryset filter kwargs builder for representative-comic
# resolution. Keys mirror the v4 ``collection`` vocabulary but use the
# singular noun the URL emits. ``comic`` and ``custom`` are handled
# directly by the cover views and never enter this map.
_GROUP_COMIC_FILTER: Final = {
    "publisher": "publisher_id",
    "imprint": "imprint_id",
    "series": "series_id",
    "volume": "volume_id",
    "folder": "folders",
    "arc": "story_arc_numbers__story_arc_id",
}

_RETRY_AFTER_SECONDS: Final = 2
_WEBP_CONTENT_TYPE: Final = "image/webp"


class WEBPRenderer(BaseRenderer):
    """Render WEBP images."""

    media_type = _WEBP_CONTENT_TYPE
    format = "webp"
    charset: str | None = None
    render_style = "binary"

    @override
    def render(self, data, *_args, **_kwargs) -> Any:
        """Return raw data."""
        return data


class _CoverBaseView(AuthFilterAPIView):
    """Shared cover-by-pk plumbing."""

    renderer_classes: Sequence[type[BaseRenderer]] = (WEBPRenderer,)
    content_type = _WEBP_CONTENT_TYPE

    @staticmethod
    def _missing_cover_response(
        status_code: int = status.HTTP_404_NOT_FOUND,
    ) -> HttpResponse:
        """
        Return an empty response for a missing or pending cover.

        Default 404 lets the web client fall back to its ``lazy-src`` SVG
        and OPDS clients use their own default rendering. ``no-store``
        prevents reverse proxies from caching the 404 briefly, which would
        otherwise delay a cover from appearing once the cover thread writes
        the real bytes. Callers using 202 add ``Retry-After`` for the
        polling loop; ``no-store`` already keeps the polling fetch reaching
        the backend.
        """
        response = HttpResponse(
            b"", content_type=_WEBP_CONTENT_TYPE, status=status_code
        )
        response["Cache-Control"] = "no-store"
        return response

    @classmethod
    def _get_cover_response(cls, pk: int, *, custom: bool) -> HttpResponse:
        """Return a cached cover, enqueue one (202), or 404."""
        cover_path = CoverPathMixin.get_cover_path(pk, custom=custom)
        # Single read — no exists()/stat() race window. The cover thread
        # writes atomically via os.replace, so we only ever see the old state
        # or the complete new file.
        try:
            cover_bytes = cover_path.read_bytes()
        except FileNotFoundError:
            cover_bytes = None
        except OSError as exc:
            logger.warning(f"Cover read error (pk={pk} custom={custom}): {exc!r}")
            cover_bytes = None

        if cover_bytes:
            return HttpResponse(cover_bytes, content_type=_WEBP_CONTENT_TYPE)
        if cover_bytes == b"":
            # Zero-byte marker = the cover thread already tried and failed.
            return cls._missing_cover_response()

        # Defer creation to the cover thread; respond 202 so the web client
        # polls until the real thumb is ready.
        try:
            LIBRARIAN_QUEUE.put(CoverCreateTask(pks=(pk,), custom=custom))
        except Exception as exc:
            logger.warning(f"Cover enqueue failed (pk={pk} custom={custom}): {exc!r}")
        response = cls._missing_cover_response(status.HTTP_202_ACCEPTED)
        response["Retry-After"] = str(_RETRY_AFTER_SECONDS)
        return response


class CoverView(_CoverBaseView):
    """Serve a single comic's cover by comic pk, ACL-checked."""

    TARGET: str = "cover"

    @extend_schema(responses={(200, _WEBP_CONTENT_TYPE): OpenApiTypes.BINARY})
    def get(self, *_args, pk: int, **_kwargs) -> HttpResponse:
        """Get the cover for a single comic pk."""
        try:
            acl_q = self.get_acl_filter(Comic, self.request.user)
            if not Comic.objects.filter(acl_q, pk=pk).exists():
                return self._missing_cover_response()
            return self._get_cover_response(pk, custom=False)
        except Exception:
            logger.exception(f"Get comic cover by pk {pk}")
            return self._missing_cover_response()


class CustomCoverView(_CoverBaseView):
    """
    Serve a CustomCover by its pk.

    No ACL check — custom covers are admin-provisioned artwork for groups,
    not comic content.
    """

    TARGET: str = "cover"

    @extend_schema(responses={(200, _WEBP_CONTENT_TYPE): OpenApiTypes.BINARY})
    def get(self, *_args, pk: int, **_kwargs) -> HttpResponse:
        """Get the custom cover for a single CustomCover pk."""
        try:
            return self._get_cover_response(pk, custom=True)
        except Exception:
            logger.exception(f"Get custom cover by pk {pk}")
            return self._missing_cover_response()


def _resolve_collection_comic_pk(source: str, pk: int, user) -> int | None:
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
    resp = HttpResponse(b"", content_type=_WEBP_CONTENT_TYPE, status=404)
    resp["Cache-Control"] = "no-store"
    return resp


def cover_dispatch_by_source(request, source: str, pk: int) -> HttpResponse:
    """Route ``/api/v4/covers/{source}/{id}`` by source kind."""
    if source == "comic":
        return CoverView.as_view()(request, pk=pk)
    if source == "custom":
        return CustomCoverView.as_view()(request, pk=pk)
    comic_pk = _resolve_collection_comic_pk(source, pk, request.user)
    if comic_pk is None:
        return _missing_cover_404()
    return CoverView.as_view()(request, pk=comic_pk)

"""
Per-pk cover endpoints.

Serve a single already-resolved cover pk — no collection filter, no ordering,
no fuzzy sort_name matching. The browser response pre-computes the
representative comic pk per card (see :mod:`codex.views.browser.annotate.cover`),
so the per-card cover URL is a cheap single-row lookup instead of re-running
the collection-resolution pipeline 72x per page.

Cover generation is never run inline. If the cached thumb is missing we
enqueue a :class:`CoverCreateTask` on the librarian queue and respond 202
Accepted with ``Retry-After`` so the client has something to render while
the cover thread produces the real bytes. When a cover can't be produced
(or doesn't exist) we respond 404 with an empty body — the web client
falls back to its ``lazy-src`` SVG and OPDS clients use their own default
rendering.

These endpoints deliberately carry no ``cache_page``. The thumb is already
a file on disk, so a server-side copy of the response body only duplicated
it — once per user, because the page-cache key hashes the ``Vary`` header
values — and it could not be invalidated for one pk, only by clearing the
whole default cache (which import finish, tag writes, and Library / Group
CRUD all do). Instead each response carries ``ETag`` and ``Last-Modified``
derived from the thumb's size and mtime, so a revalidating client gets a
304 without the bytes being read, and a regenerated cover invalidates
itself.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final, override

from django.http import HttpResponse
from django.utils.cache import get_conditional_response
from django.utils.http import http_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from loguru import logger
from rest_framework import status
from rest_framework.renderers import BaseRenderer

from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.covers.tasks import CoverCreateTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models import Comic
from codex.urls.const import COVER_MAX_AGE
from codex.views.auth import AuthFilterAPIView, GroupACLMixin

# source → queryset filter kwargs builder for representative-comic
# resolution. Keys mirror the v4 ``collection`` vocabulary but use the
# singular noun the URL emits. ``comic`` and ``custom`` are handled
# directly by the cover views and never enter this map.
_COLLECTION_COMIC_FILTER: Final = {
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
    # A page of covers is dozens of sub-requests for one page view, not dozens
    # of user actions. Until this view served conditional GETs, ``cache_page``
    # short-circuited before DRF ever dispatched, so cover hits never reached
    # the throttles; counting them now would let a single browse page exhaust
    # an admin's configured ``throttle.user`` rate.
    throttle_classes = ()

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

    @staticmethod
    def _cover_validators(cover_path: Path) -> tuple[str, int] | None:
        """Return the (ETag, Last-Modified) pair for a present, non-empty cover."""
        try:
            stat = cover_path.stat()
        except OSError:
            # Absent, or unreadable — the byte read below decides what to do.
            return None
        if not stat.st_size:
            # Zero-byte marker; nothing to validate against.
            return None
        # The cover thread rewrites the whole file, so size + mtime identify
        # the bytes. Seconds resolution for Last-Modified, which is all an
        # HTTP-date carries.
        return f'"{stat.st_mtime_ns}-{stat.st_size}"', int(stat.st_mtime)

    @classmethod
    def _add_cover_headers(
        cls, response: HttpResponse, validators: tuple[str, int], *, custom: bool
    ) -> HttpResponse:
        """Attach the revalidation and freshness headers for a served cover."""
        etag, last_modified = validators
        response["ETag"] = etag
        response["Last-Modified"] = http_date(last_modified)
        # Comic covers are ACL-gated, so only the requesting user's own browser
        # may store them; a shared proxy holding one would serve it to readers
        # the ACL excludes. Custom covers are admin-provisioned collection
        # artwork with no ACL (see CustomCoverView), so they stay public.
        visibility = "public" if custom else "private"
        response["Cache-Control"] = f"{visibility}, max-age={COVER_MAX_AGE}"
        return response

    @classmethod
    def _get_cover_response(cls, request, pk: int, *, custom: bool) -> HttpResponse:
        """Return a cover (200 or 304), enqueue one (202), or 404."""
        cover_path = CoverPathMixin.get_cover_path(pk, custom=custom)
        # stat() before the read so a revalidating client is answered with a
        # 304 without the image bytes ever being touched. The cover thread
        # writes atomically via os.replace, so a file swapped between the stat
        # and the read hands back the new bytes under the previous ETag: the
        # client stores the fresh image and revalidates against the new ETag on
        # the next request, so the pair is self-correcting.
        validators = cls._cover_validators(cover_path)
        if validators:
            etag, last_modified = validators
            not_modified = get_conditional_response(
                request, etag=etag, last_modified=last_modified
            )
            if not_modified is not None:
                return cls._add_cover_headers(not_modified, validators, custom=custom)

        try:
            cover_bytes = cover_path.read_bytes()
        except FileNotFoundError:
            cover_bytes = None
        except OSError as exc:
            logger.warning(f"Cover read error (pk={pk} custom={custom}): {exc!r}")
            cover_bytes = None

        if cover_bytes:
            response = HttpResponse(cover_bytes, content_type=_WEBP_CONTENT_TYPE)
            if validators:
                cls._add_cover_headers(response, validators, custom=custom)
            return response
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
            return self._get_cover_response(self.request, pk, custom=False)
        except Exception:
            logger.exception(f"Get comic cover by pk {pk}")
            return self._missing_cover_response()


class CustomCoverView(_CoverBaseView):
    """
    Serve a CustomCover by its pk.

    No ACL check — custom covers are admin-provisioned artwork for collections,
    not comic content.
    """

    TARGET: str = "cover"

    @extend_schema(responses={(200, _WEBP_CONTENT_TYPE): OpenApiTypes.BINARY})
    def get(self, *_args, pk: int, **_kwargs) -> HttpResponse:
        """Get the custom cover for a single CustomCover pk."""
        try:
            return self._get_cover_response(self.request, pk, custom=True)
        except Exception:
            logger.exception(f"Get custom cover by pk {pk}")
            return self._missing_cover_response()


def _resolve_collection_comic_pk(source: str, pk: int, user) -> int | None:
    """Pick a representative comic pk for a collection source, ACL-aware."""
    field = _COLLECTION_COMIC_FILTER.get(source)
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

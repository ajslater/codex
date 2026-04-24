"""
Per-pk cover endpoints.

Serve a single already-resolved cover pk — no group filter, no ordering,
no fuzzy sort_name matching. The browser response pre-computes the
representative comic pk per card (see :mod:`codex.views.browser.annotate.cover`),
so the per-card cover URL is a cheap single-row lookup instead of re-running
the group-resolution pipeline 72x per page.

Cover generation is never run inline. If the cached thumb is missing we
enqueue a :class:`CoverCreateTask` on the librarian queue and respond 202
Accepted with ``Retry-After`` plus a placeholder image so the client has
something to render while the cover thread produces the real bytes.
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
from codex.views.auth import AuthFilterAPIView
from codex.views.const import MISSING_COVER_PATH

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
        status_code: int = status.HTTP_200_OK,
    ) -> HttpResponse:
        body = MISSING_COVER_PATH.read_bytes()
        return HttpResponse(body, content_type=_WEBP_CONTENT_TYPE, status=status_code)

    @classmethod
    def _get_cover_response(cls, pk: int, *, custom: bool) -> HttpResponse:
        """Return a cached cover or enqueue one and return 202 Retry-After."""
        cover_path = CoverPathMixin.get_cover_path(pk, custom=custom)
        if cover_path.exists():
            if cover_path.stat().st_size > 0:
                return HttpResponse(
                    cover_path.read_bytes(), content_type=_WEBP_CONTENT_TYPE
                )
            # Zero-byte marker = the cover thread already tried and failed.
            return cls._missing_cover_response()

        # Defer creation to the cover thread; respond with a placeholder.
        # Cache-Control: no-store prevents the browser from caching the
        # placeholder at this URL so a subsequent fetch to the same URL (once
        # the cover thread has written the real thumb) actually hits the
        # network instead of serving the stale placeholder.
        LIBRARIAN_QUEUE.put(CoverCreateTask(pks=(pk,), custom=custom))
        response = cls._missing_cover_response(status.HTTP_202_ACCEPTED)
        response["Retry-After"] = str(_RETRY_AFTER_SECONDS)
        response["Cache-Control"] = "no-store"
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
            logger.exception("Get comic cover by pk")
            raise


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
            logger.exception("Get custom cover by pk")
            raise

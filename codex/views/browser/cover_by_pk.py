"""
Thin per-pk cover endpoints.

These serve a single already-resolved cover pk — no group filter, no
ordering, no fuzzy sort_name matching. The browser response now
pre-computes the representative comic pk per card (see
``BrowserAnnotateCoverView``), so the per-card cover URL is a cheap
single-row lookup instead of re-running the group-resolution pipeline
72x per page.
"""

from collections.abc import Sequence
from typing import Any

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from loguru import logger
from rest_framework.renderers import BaseRenderer

from codex.librarian.covers.create import CoverCreateThread
from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models import Comic
from codex.views.auth import AuthFilterAPIView
from codex.views.browser.cover import WEBPRenderer
from codex.views.const import MISSING_COVER_FN, STATIC_IMG_PATH


class _CoverByPkBaseView(AuthFilterAPIView):
    """Shared cover-by-pk plumbing."""

    renderer_classes: Sequence[type[BaseRenderer]] = (WEBPRenderer,)
    content_type = "image/webp"

    @staticmethod
    def _get_cover_bytes(pk: int, *, custom: bool) -> tuple[Any, str]:
        """Resolve the cover path and return (body, content_type)."""
        cover_path = CoverPathMixin.get_cover_path(pk, custom=custom)
        if not cover_path.exists():
            thumb_buffer = CoverCreateThread.create_cover_from_path(
                pk, str(cover_path), logger, LIBRARIAN_QUEUE, custom=custom
            )
            if thumb_buffer:
                return thumb_buffer, "image/webp"
        elif cover_path.stat().st_size > 0:
            return cover_path.read_bytes(), "image/webp"

        missing_path = STATIC_IMG_PATH / MISSING_COVER_FN
        return missing_path.read_bytes(), "image/webp"


class ComicCoverByPkView(_CoverByPkBaseView):
    """Serve a single comic's cover by comic pk, ACL-checked."""

    TARGET: str = "cover"

    @extend_schema(responses={(200, "image/webp"): OpenApiTypes.BINARY})
    def get(self, *_args, pk: int, **_kwargs) -> HttpResponse:
        """Get the cover for a single comic pk."""
        try:
            acl_q = self.get_acl_filter(Comic, self.request.user)
            if not Comic.objects.filter(acl_q, pk=pk).exists():
                pk = 0
            body, content_type = self._get_cover_bytes(pk, custom=False)
            return HttpResponse(body, content_type=content_type)
        except Exception:
            logger.exception("Get comic cover by pk")
            raise


class CustomCoverByPkView(_CoverByPkBaseView):
    """
    Serve a CustomCover by its pk.

    No ACL check — matches parity with the existing ``CoverView`` path,
    which also resolves custom covers purely by group membership without
    consulting the age-rating / library ACL. Custom covers are admin-
    provisioned artwork for groups, not comic content.
    """

    TARGET: str = "cover"

    @extend_schema(responses={(200, "image/webp"): OpenApiTypes.BINARY})
    def get(self, *_args, pk: int, **_kwargs) -> HttpResponse:
        """Get the custom cover for a single CustomCover pk."""
        try:
            body, content_type = self._get_cover_bytes(pk, custom=True)
            return HttpResponse(body, content_type=content_type)
        except Exception:
            logger.exception("Get custom cover by pk")
            raise

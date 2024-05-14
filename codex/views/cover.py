"""Comic cover thumbnail view."""

from typing import ClassVar

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.renderers import BaseRenderer
from rest_framework.views import APIView

from codex.librarian.covers.create import CoverCreateMixin
from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.views.auth import GroupACLMixin, IsAuthenticatedOrEnabledNonUsers
from codex.views.const import MISSING_COVER_FN, MISSING_COVER_NAME_MAP, STATIC_IMG_PATH

LOG = get_logger(__name__)


class WEBPRenderer(BaseRenderer):
    """Render WEBP images."""

    media_type = "image/webp"
    format = "webp"
    charset = None
    render_style = "binary"

    def render(self, data, *_args, **_kwargs):
        """Return raw data."""
        return data


class CoverView(APIView, GroupACLMixin):
    """ComicCover View."""

    permission_classes: ClassVar[list] = [IsAuthenticatedOrEnabledNonUsers]  # type: ignore
    renderer_classes = (WEBPRenderer,)
    content_type = "image/webp"

    def _get_missing_cover_path(self):
        # Get the missing cover, which is a default svg if fetched for a group.
        data = self.request.GET
        group: str = data.get("group", "c")  # type: ignore
        cover_name = MISSING_COVER_NAME_MAP.get(group)
        if cover_name:
            cover_fn = cover_name + ".svg"
            content_type = "image/svg+xml"
        else:
            cover_fn = MISSING_COVER_FN
            content_type = "image/webp"
        cover_path = STATIC_IMG_PATH / cover_fn
        return cover_path, content_type

    @extend_schema(responses={(200, content_type): OpenApiTypes.BINARY})
    def get(self, *_args, **_kwargs):
        """Get comic cover."""
        thumb_image_data = None
        content_type = "image/webp"

        pk = self.kwargs.get("pk")
        cover_path = CoverPathMixin.get_cover_path(pk)
        if not cover_path.exists():
            thumb_image_data = CoverCreateMixin.create_cover_from_path(
                pk, cover_path, LOG, LIBRARIAN_QUEUE
            )
            if not thumb_image_data:
                cover_path, content_type = self._get_missing_cover_path()
        elif cover_path.stat().st_size == 0:
            cover_path, content_type = self._get_missing_cover_path()

        if not thumb_image_data:
            # if not thumb_image_data:
            with cover_path.open("rb") as f:
                thumb_image_data = f.read()

        return HttpResponse(thumb_image_data, content_type=content_type)

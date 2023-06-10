"""Comic cover thumbnail view."""
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.renderers import BaseRenderer
from rest_framework.views import APIView

from codex.librarian.covers.create import CoverCreateMixin
from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.mixins import GroupACLMixin

LOG = get_logger(__name__)


class WEBPRenderer(BaseRenderer):
    """Render WEBP images."""

    media_type = "image/webp"
    format = "webp"  # noqa A003
    charset = None
    render_style = "binary"

    def render(self, data, *args, **kwargs):
        """Return raw data."""
        return data


class CoverView(APIView, GroupACLMixin):
    """ComicCover View."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
    renderer_classes = (WEBPRenderer,)
    content_type = "image/webp"

    @extend_schema(responses={(200, content_type): OpenApiTypes.BINARY})
    def get(self, *args, **kwargs):
        """Get comic cover."""
        # thumb_image_data = None
        pk = self.kwargs.get("pk")
        cover_path = CoverPathMixin.get_cover_path(pk)
        thumb_image_data = None
        if not cover_path.exists():
            thumb_image_data = CoverCreateMixin.create_cover_from_path(
                pk, cover_path, LOG, LIBRARIAN_QUEUE
            )
            if not thumb_image_data:
                cover_path = CoverPathMixin.MISSING_COVER_PATH

        if not thumb_image_data:
            # if not thumb_image_data:
            with cover_path.open("rb") as f:
                thumb_image_data = f.read()

        return HttpResponse(thumb_image_data, content_type=self.content_type)

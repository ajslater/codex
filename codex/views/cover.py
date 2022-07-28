"""Comic cover thumbnail view."""
from django.http import HttpResponse
from rest_framework.views import APIView

from codex.librarian.covers.create import create_cover
from codex.librarian.covers.path import MISSING_COVER_PATH, get_cover_path
from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.settings.logging import get_logger
from codex.views.group_filter import GroupACLMixin


LOG = get_logger(__name__)


class CoverView(APIView, GroupACLMixin):
    """ComicCover View."""

    def get(self, request, *args, **kwargs):
        """Get comic cover."""
        thumb_image_data = None
        pk = self.kwargs.get("pk")
        cover_path = get_cover_path(pk)
        if not cover_path.exists():
            task = create_cover(pk, cover_path)
            LIBRARIAN_QUEUE.put(task)
            thumb_image_data = task.data
            if not thumb_image_data:
                cover_path = MISSING_COVER_PATH

        if not thumb_image_data:
            with cover_path.open("rb") as f:
                thumb_image_data = f.read()
        return HttpResponse(thumb_image_data, content_type="image/webp")

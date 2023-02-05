"""Comic cover thumbnail view."""
import math

from time import sleep, time

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.renderers import BaseRenderer
from rest_framework.views import APIView

from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.covers.tasks import NewCoverCreateTask
from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.views.mixins import GroupACLMixin


class WEBPRenderer(BaseRenderer):
    """Render WEBP images."""

    media_type = "image/webp"
    format = "webp"
    charset = None
    render_style = "binary"

    def render(self, data, *args, **kwargs):
        """Return raw data."""
        return data


class CoverView(APIView, GroupACLMixin):
    """ComicCover View."""

    renderer_classes = (WEBPRenderer,)
    content_type = "image/webp"
    RENDER_WAIT_TIME = 0.002
    WAIT_BACKOFF_POWER = math.log(2)

    @extend_schema(responses={(200, content_type): OpenApiTypes.BINARY})
    def get(self, request, *args, **kwargs):
        """Get comic cover."""
        # thumb_image_data = None
        pk = self.kwargs.get("pk")
        cover_path = CoverPathMixin.get_cover_path(pk)
        if not cover_path.exists():
            # task, exc = create_cover(pk, cover_path)
            task = NewCoverCreateTask(pk)
            LIBRARIAN_QUEUE.put(task)
            # TODO best thing to here would be to wait and call back when it's written.
            # launch checker tasks with browser and metadata. not this.
            #   browser sends bulk create to librarian.
            # TODO for now just wait:
            elapsed = 0
            wait_time = self.RENDER_WAIT_TIME
            start = time()
            while not cover_path.exists():
                sleep(wait_time)  # TODO time the average and minimum
                # TODO try again with browser pre-job?
                elapsed = time() - start
                if elapsed >= 3:
                    cover_path = CoverPathMixin.MISSING_COVER_PATH
                wait_time = wait_time**self.WAIT_BACKOFF_POWER
            print(f"cover view {pk} took {elapsed} seconds")

        # if not thumb_image_data:
        with cover_path.open("rb") as f:
            thumb_image_data = f.read()

        return HttpResponse(thumb_image_data, content_type=self.content_type)

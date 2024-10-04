"""Views for reading comic books."""

from io import BytesIO

from comicbox.box import Comicbox
from django.http.response import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.negotiation import BaseContentNegotiation

from codex.librarian.bookmark.tasks import BookmarkUpdateTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.models.comic import Comic, FileType
from codex.settings.settings import FALSY
from codex.views.bookmark import BookmarkBaseView
from codex.views.util import chunker

LOG = get_logger(__name__)
_PDF_MIME_TYPE = "application/pdf"
# Most pages seem to be 2.5 Mb
# largest pages I've seen were 9 Mb
_PAGE_CHUNK_SIZE = (1024**2) * 3  # 3 Mb


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    """Hack for clients with wild accept headers."""

    def select_parser(self, request, parsers):  # noqa: ARG002
        """Select the first parser in the `.parser_classes` list."""
        return next(iter(parsers))

    def select_renderer(  # type: ignore
        self,
        request,  # noqa: ARG002
        renderers,
        _format_suffix="",
    ):
        """Select the first renderer in the `.renderer_classes` list."""
        renderer = next(iter(renderers))
        return (renderer, renderer.media_type)


class ReaderPageView(BookmarkBaseView):
    """Display a comic page from the archive itself."""

    X_MOZ_PRE_HEADERS = frozenset({"prefetch", "preload", "prerender", "subresource"})
    content_type = "image/jpeg"
    content_negotiation_class = IgnoreClientContentNegotiation  # type: ignore

    def _update_bookmark(self):
        """Update the bookmark if the bookmark param was passed."""
        do_bookmark = bool(
            self.request.GET.get("bookmark")
            and self.request.headers.get("X-moz") not in self.X_MOZ_PRE_HEADERS
        )
        if not do_bookmark:
            return

        auth_filter = self.get_bookmark_auth_filter()
        pk = self.kwargs.get("pk")
        comic_filter = {"pk": pk}
        page = self.kwargs.get("page")
        updates = {"page": page}

        task = BookmarkUpdateTask(auth_filter, comic_filter, updates)
        LIBRARIAN_QUEUE.put(task)

    def _get_page_image(self):
        """Get the image data and content type."""
        group_acl_filter = self.get_group_acl_filter(Comic, self.request.user)
        pk = self.kwargs.get("pk")
        comic = Comic.objects.filter(group_acl_filter).only("path").get(pk=pk)
        page = self.kwargs.get("page")
        to_pixmap = self.request.GET.get("pixmap", "").lower() not in FALSY
        if comic.file_type == FileType.PDF.value and not to_pixmap:
            content_type = _PDF_MIME_TYPE
        else:
            content_type = self.content_type

        with Comicbox(comic.path) as cb:
            page_image = cb.get_page_by_index(page, to_pixmap=to_pixmap)
        if not page_image:
            page_image = b""

        return page_image, content_type

    @extend_schema(
        parameters=[
            OpenApiParameter("bookmark", OpenApiTypes.BOOL, default=True),
            OpenApiParameter("pixmap", OpenApiTypes.BOOL, default=False),
        ],
        responses={
            (200, content_type): OpenApiTypes.BINARY,
            (200, _PDF_MIME_TYPE): OpenApiTypes.BINARY,
        },
    )
    def get(self, *_args, **_kwargs):
        """Get the comic page from the archive."""
        try:
            page_image, content_type = self._get_page_image()
            self._update_bookmark()
        except Comic.DoesNotExist as exc:
            pk = self.kwargs.get("pk")
            detail = f"comic {pk} not found in db."
            raise NotFound(detail=detail) from exc
        except FileNotFoundError as exc:
            pk = self.kwargs.get("pk")
            detail = f"comic path for {pk} not found: {exc}."
            raise NotFound(detail=detail) from exc
        except Exception as exc:
            LOG.warning(exc)
            raise NotFound(detail="comic page not found") from exc
        else:
            page_chunker = chunker(BytesIO(page_image), _PAGE_CHUNK_SIZE)
            return StreamingHttpResponse(page_chunker, content_type=content_type)

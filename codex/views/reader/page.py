"""Views for reading comic books."""
from comicbox.comic_archive import ComicArchive
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.negotiation import BaseContentNegotiation

from codex.logger.logging import get_logger
from codex.models import Comic
from codex.pdf import PDF
from codex.version import COMICBOX_CONFIG
from codex.views.bookmark import BookmarkBaseView

LOG = get_logger(__name__)


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    """Hack for clients with wild accept headers."""

    def select_parser(self, _request, parsers):
        """Select the first parser in the `.parser_classes` list."""
        return parsers[0]

    def select_renderer(self, _request, renderers, _format_suffix):
        """Select the first renderer in the `.renderer_classes` list."""
        return (renderers[0], renderers[0].media_type)


class ReaderPageView(BookmarkBaseView):
    """Display a comic page from the archive itself."""

    X_MOZ_PRE_HEADERS = {"prefetch", "preload", "prerender", "subresource"}
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
        page = self.kwargs.get("page")
        updates = {"page": page}
        pk = self.kwargs.get("pk")
        comic_filter = {"pk": pk}
        self.update_bookmarks(updates, comic_filter)

    def _get_page_image(self):
        """Get the image data and content type."""
        group_acl_filter = self.get_group_acl_filter(True)
        pk = self.kwargs.get("pk")
        comic = Comic.objects.filter(group_acl_filter).only("path").get(pk=pk)
        page = self.kwargs.get("page")
        if comic.file_type == Comic.FileType.PDF.value:
            car = PDF(comic.path)
            content_type = PDF.MIME_TYPE
        else:
            car = ComicArchive(comic.path, config=COMICBOX_CONFIG)
            content_type = self.content_type
        page_image = car.get_page_by_index(page)
        return page_image, content_type

    @extend_schema(
        responses={
            (200, content_type): OpenApiTypes.BINARY,
            (200, PDF.MIME_TYPE): OpenApiTypes.BINARY,
        }
    )
    def get(self, *args, **kwargs):
        """Get the comic page from the archive."""
        pk = self.kwargs.get("pk")
        comic = None
        try:
            page_image, content_type = self._get_page_image()
            self._update_bookmark()
        except Comic.DoesNotExist as exc:
            detail = f"comic {pk} not found in db."
            raise NotFound(detail=detail) from exc
        except FileNotFoundError as exc:
            path = comic.path if comic else f"path for {pk}"
            detail = f"comic {path} not found."
            raise NotFound(detail=detail) from exc
        except Exception as exc:
            LOG.warning(exc)
            raise NotFound(detail="comic page not found") from exc
        else:
            return HttpResponse(page_image, content_type=content_type)

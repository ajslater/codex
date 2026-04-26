"""Views for reading comic books."""

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from loguru import logger
from pdffile import PageFormat
from rest_framework.exceptions import NotFound

from codex.librarian.bookmark.tasks import BookmarkUpdateTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models.choices import FileTypeChoices
from codex.models.comic import Comic
from codex.settings import FALSY
from codex.views.auth import AuthFilterAPIView
from codex.views.bookmark import BookmarkAuthMixin
from codex.views.reader._archive_cache import archive_cache

_PDF_MIME_TYPE = "application/pdf"
_PDF_FORMAT_NON_PDF_TYPES = frozenset(
    {e.value for e in (PageFormat.PIXMAP, PageFormat.IMAGE)}
)


class ReaderPageView(BookmarkAuthMixin, AuthFilterAPIView):
    """Display a comic page from the archive itself."""

    X_MOZ_PRE_HEADERS = frozenset({"prefetch", "preload", "prerender", "subresource"})
    content_type = "image/jpeg"

    def _update_bookmark(self) -> None:
        """Update the bookmark if the bookmark param was passed."""
        do_bookmark = bool(
            self.request.GET.get("bookmark")
            and self.request.headers.get("X-moz") not in self.X_MOZ_PRE_HEADERS
        )
        if not do_bookmark:
            return

        auth_filter = self.get_bookmark_auth_filter()
        comic_pks = (self.kwargs.get("pk"),)
        page = self.kwargs.get("page")
        updates = {"page": page}

        task = BookmarkUpdateTask(auth_filter, comic_pks, updates)
        LIBRARIAN_QUEUE.put(task)

    def _get_page_image(self) -> tuple:
        """Get the image data and content type."""
        # ``.get(pk=...)`` collapses any duplicates an ACL JOIN might
        # introduce; the explicit ``.distinct()`` on a single-row
        # fetch is redundant (sub-plan 03 #6).
        acl_filter = self.get_acl_filter(Comic, self.request.user)
        qs = Comic.objects.filter(acl_filter).only("path", "file_type")
        pk = self.kwargs.get("pk")
        comic = qs.get(pk=pk)

        # page_image
        page = self.kwargs.get("page")
        pdf_format = (
            PageFormat.PIXMAP.value
            if self.request.GET.get("pixmap", "").lower() not in FALSY
            else ""
        )
        # Process-wide LRU of open Comicbox archives — the web reader's
        # prev/curr/next prefetch fires 3-5 page hits on the same archive
        # within a second, and ``cacheBook`` mode bursts a whole-book
        # prefetch (N parallel page hits). Without the cache, every hit
        # re-opens the archive (sub-plan 03 #1). The per-archive lock
        # held inside ``archive_cache.open(...)`` serializes extraction
        # because ZipFile / RarFile / PDF backends aren't thread-safe.
        with archive_cache.open(comic.path) as cb:
            page_image = cb.get_page_by_index(page, pdf_format=pdf_format)
        if not page_image:
            page_image = b""

        # content type
        if (
            comic.file_type == FileTypeChoices.PDF.value  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            and pdf_format not in _PDF_FORMAT_NON_PDF_TYPES
        ):
            content_type = _PDF_MIME_TYPE
        else:
            content_type = self.content_type

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
    def get(self, *_args, **_kwargs) -> HttpResponse:
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
            logger.warning(exc)
            raise NotFound(detail="comic page not found") from exc
        else:
            return HttpResponse(page_image, content_type=content_type)

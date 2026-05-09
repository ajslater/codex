"""Views for reading comic books."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Final

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from loguru import logger
from pdffile import PageMode, PDFFile
from rest_framework.exceptions import NotFound

from codex.librarian.bookmark.tasks import BookmarkUpdateTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models.choices import FileTypeChoices
from codex.models.comic import Comic
from codex.views.auth import AuthFilterAPIView
from codex.views.bookmark import BookmarkAuthMixin
from codex.views.reader._archive_cache import archive_cache, page_acl_cache

if TYPE_CHECKING:
    from pdffile import PageVerdict

    from codex.views.reader._archive_cache import _ArchiveEntry

_PDF_MIME_TYPE: Final[str] = "application/pdf"

#: Query-parameter name that selects the PDF serving mode. Picked to
#: avoid colliding with DRF's reserved ``?format=`` (``URL_FORMAT_OVERRIDE``)
#: which DRF interprets as a renderer-format selector — it raises
#: ``NotFound`` for unknown values *before* the view's ``get`` runs.
_SERVE_PARAM: Final[str] = "serve"

#: Permitted ``?serve=`` values. ``auto`` runs the detector; ``pdf``
#: skips the detector and forces the legacy single-page-PDF path;
#: ``image`` forces a server-side rasterize (works for any PDF page
#: but spends more CPU than the detector path on vector-heavy pages).
_SERVE_AUTO: Final[str] = "auto"
_SERVE_PDF: Final[str] = "pdf"
_SERVE_IMAGE: Final[str] = "image"
_SERVE_HINTS: Final[frozenset[str]] = frozenset(
    {_SERVE_AUTO, _SERVE_PDF, _SERVE_IMAGE}
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

    def _resolve_path_and_type(self, pk) -> tuple[str, str | None]:
        """
        Resolve ``(path, file_type)`` for the requested comic, ACL-filtered.

        Caches the result per ``(auth_key, comic_pk)`` for a short TTL
        so a sequential read-through doesn't fire the ACL filter SQL on
        every page (sub-plan 03 #2 / Tier 4 #15). Cache misses fall
        through to ``Comic.objects.filter(acl_filter).get(pk=pk)``;
        ``.get`` collapses any duplicates an ACL JOIN might introduce,
        making the explicit ``.distinct()`` on a single-row fetch
        redundant (sub-plan 03 #6).
        """
        auth_filter = self.get_bookmark_auth_filter()
        # ``auth_filter`` is one of ``{"user_id": pk}`` or
        # ``{"session_id": key}``; flatten to a hashable tuple.
        auth_key = next(iter(auth_filter.items()))
        cache_key = (auth_key, pk)
        now = time.monotonic()
        cached = page_acl_cache.get(cache_key, now)
        if cached is not None:
            return cached
        acl_filter = self.get_acl_filter(Comic, self.request.user)
        qs = Comic.objects.filter(acl_filter).only("path", "file_type")
        comic = qs.get(pk=pk)
        path = comic.path
        file_type = comic.file_type
        page_acl_cache.put(cache_key, path, file_type, now)
        return path, file_type

    def _serve_hint(self) -> str:
        raw = self.request.GET.get(_SERVE_PARAM, _SERVE_AUTO).lower()
        return raw if raw in _SERVE_HINTS else _SERVE_AUTO

    @staticmethod
    def _classify_cached(entry: _ArchiveEntry, pdf: PDFFile, page: int) -> PageVerdict:
        """Memoize ``pdf.classify_page`` on the cache entry."""
        cached = entry.verdicts.get(page)
        if cached is not None:
            return cached
        verdict = pdf.classify_page(page)
        entry.verdicts[page] = verdict
        return verdict

    def _try_pdf_image_serve(
        self, path: str, page: int, serve_hint: str
    ) -> tuple[bytes, str] | None:
        """
        Image-serve fast path for PDF pages.

        Returns ``(bytes, content_type)`` when the page can be served
        as a raw image (detector matched, or caller forced ``image``);
        ``None`` when the caller should fall back to the legacy
        single-page-PDF path.
        """
        with archive_cache.open_entry(path) as entry:
            # ``Comicbox._get_archive`` returns the underlying archive
            # union (zip / rar / 7z / tar / pdf). Caller has gated on
            # ``file_type == PDF`` so the runtime type is ``PDFFile``;
            # ``isinstance`` narrows for the type checker. Private
            # comicbox API for now — swap to a public getter once one
            # lands upstream.
            archive = entry.comicbox._get_archive()  # noqa: SLF001
            if not isinstance(archive, PDFFile):
                return None
            pdf = archive
            page_index = int(page)

            if serve_hint == _SERVE_IMAGE:
                # Always-image override — pixmap fallback for vector pages.
                blob, ext = pdf.read_full_pixmap_jpeg(page_index)
                return blob, f"image/{ext}"

            verdict = self._classify_cached(entry, pdf, page_index)
            if verdict.mode is PageMode.PDF_FALLBACK:
                return None
            served = pdf.read_image_if_dominant(page_index)
            if served is None:
                # Detection said dominant but extraction failed; fall
                # through to PDF rather than serve a broken response.
                return None
            blob, ext = served
            return blob, f"image/{ext}"

    def _get_page_image(self) -> tuple[bytes, str]:
        """Get the image data and content type."""
        pk = self.kwargs.get("pk")
        path, file_type = self._resolve_path_and_type(pk)

        page = self.kwargs.get("page")
        serve_hint = self._serve_hint()

        is_pdf = file_type == FileTypeChoices.PDF.value  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]

        # Image-dominant fast path for PDFs (skipped when the caller
        # forces ``?serve=pdf``).
        if is_pdf and serve_hint != _SERVE_PDF:
            served = self._try_pdf_image_serve(path, page, serve_hint)
            if served is not None:
                return served

        # Process-wide LRU of open Comicbox archives — the web reader's
        # prev/curr/next prefetch fires 3-5 page hits on the same archive
        # within a second, and ``cacheBook`` mode bursts a whole-book
        # prefetch (N parallel page hits). Without the cache, every hit
        # re-opens the archive (sub-plan 03 #1). The per-archive lock
        # held inside ``archive_cache.open(...)`` serializes extraction
        # because ZipFile / RarFile / PDF backends aren't thread-safe.
        with archive_cache.open(path) as cb:
            page_image = cb.get_page_by_index(page, pdf_format="")
        if not page_image:
            page_image = b""

        content_type = _PDF_MIME_TYPE if is_pdf else self.content_type
        return page_image, content_type

    @extend_schema(
        parameters=[
            OpenApiParameter("bookmark", OpenApiTypes.BOOL, default=True),
            OpenApiParameter(
                _SERVE_PARAM,
                OpenApiTypes.STR,
                default=_SERVE_AUTO,
                enum=sorted(_SERVE_HINTS),
                description=(
                    "PDF serving mode: 'auto' (detector), "
                    "'pdf' (legacy single-page PDF), "
                    "'image' (always rasterize). Ignored for non-PDF archives."
                ),
            ),
        ],
        responses={
            (200, content_type): OpenApiTypes.BINARY,
            (200, "image/png"): OpenApiTypes.BINARY,
            (200, "image/webp"): OpenApiTypes.BINARY,
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

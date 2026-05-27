"""
API v4 reader & comic view endpoints.

Thin envelope wrappers over the v3 reader stack. Per
``tasks/api-v4.md``:

* ``GET /api/v4/reader/comics/{id}`` — composite view (comic + arc
  navigation + prev/next book), delegates to v3 ``ReaderView``.
* ``GET /api/v4/reader/settings`` — global reader settings only.
* ``GET/PATCH /api/v4/comics/{id}/reader-settings`` — layered scopes
  via ``?scopes=g,c,s,f,a``.
* ``PATCH /api/v4/comics/{id}/bookmark`` — single-comic bookmark
  delegating to v3 ``BookmarkView`` with ``group="c"`` synthesized.

Binary endpoints (page/cover/download) are intentionally **not**
re-imagined — the plan keeps them on REST without envelope. v4 just
re-mounts them under the new prefix so callers can use a consistent
base URL.
"""

from typing import TYPE_CHECKING, override

from codex.views.browser.bookmark import BookmarkView
from codex.views.browser.cover import CoverView
from codex.views.download import DownloadView
from codex.views.reader.page import ReaderPageView
from codex.views.reader.reader import ReaderView
from codex.views.reader.settings import ReaderSettingsView
from codex.views.v4.common import EnvelopeJSONRenderer

if TYPE_CHECKING:
    from rest_framework.request import Request


class V4ReaderComicView(ReaderView):
    """``GET /api/v4/reader/comics/{id}`` — composite reader payload."""

    renderer_classes = (EnvelopeJSONRenderer,)


class V4ReaderSettingsGlobalView(ReaderSettingsView):
    """``GET|PATCH /api/v4/reader/settings`` — global reader settings."""

    renderer_classes = (EnvelopeJSONRenderer,)


class V4ComicReaderSettingsView(ReaderSettingsView):
    """
    ``GET|PATCH /api/v4/comics/{id}/reader-settings``.

    Accepts ``?scopes=g,c,s,f,a`` to layer multiple scopes in one
    response. The PATCH body picks the target scope explicitly via
    ``scope``/``scope_pk`` — same as v3.
    """

    renderer_classes = (EnvelopeJSONRenderer,)


class V4ComicBookmarkView(BookmarkView):
    """
    ``PATCH /api/v4/comics/{id}/bookmark`` — single-comic bookmark.

    Synthesizes ``group="c"`` and ``pks=(id,)`` so the v3 ``BookmarkView``
    body can run untouched. Body is ``{page, finished}``.
    """

    renderer_classes = (EnvelopeJSONRenderer,)

    if TYPE_CHECKING:
        kwargs: dict

    @override
    def initial(self, request: "Request", *args, **kwargs):
        """Synthesize v3 (group, pks) kwargs before BookmarkView dispatch."""
        pk = self.kwargs.pop("pk", None)
        self.kwargs["group"] = "c"
        self.kwargs["pks"] = (pk,) if pk is not None else ()
        super().initial(request, *args, **kwargs)


class V4ComicPageView(ReaderPageView):
    """``GET /api/v4/comics/{id}/pages/{n}`` — binary, no envelope."""


class V4ComicCoverView(CoverView):
    """``GET /api/v4/comics/{id}/cover`` — binary, no envelope."""


class V4ComicDownloadView(DownloadView):
    """``GET /api/v4/comics/{id}/download/{filename}`` — binary, no envelope."""

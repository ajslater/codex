"""
API v4 browser view endpoints — Option A path routing.

The v4 routes accept ``/api/v4/browse/{collection}[/{parentIds}]``
(plural-English collection, omitted segment = root, no magic
``pks=0``). Underneath, the v3 view bodies handle the heavy lifting;
v4 dispatch translates URL kwargs from the v4 shape back into the
v3 ``(group, pks, page)`` triple before delegating.

The v3 ``BrowserView``'s dual ``groups``/``books``/``rows``
serialization (called out in ``tasks/api-v4.md``) is *not* unpacked
here — that's a meaningful body change deferred to a follow-up under
the same Phase 3 banner. This commit lands the URL contract and the
envelope; the serialization simplification can land independently
without breaking either.
"""

from typing import TYPE_CHECKING, override

from codex.urls.converters import COLLECTION_TO_GROUP
from codex.views.browser.bookmark import BookmarkView
from codex.views.browser.browser import BrowserView
from codex.views.browser.choices import (
    BrowserChoicesAvailableView,
    BrowserChoicesView,
)
from codex.views.browser.download import GroupDownloadView
from codex.views.browser.force_update import ForceUpdateView
from codex.views.browser.metadata import MetadataView
from codex.views.browser.saved_settings import (
    SavedBrowserSettingsListView,
    SavedBrowserSettingsLoadView,
)
from codex.views.browser.settings import BrowserSettingsView
from codex.views.lazy_import import LazyImportView
from codex.views.v4.common import EnvelopeJSONRenderer

if TYPE_CHECKING:
    from rest_framework.request import Request


class _V4BrowseTranslateMixin:
    """
    Translate v4 URL kwargs into the v3 ``(group, pks, page)`` shape.

    The mixin pops ``collection`` and ``parent_ids`` off ``self.kwargs``
    before the view body runs, and back-fills ``group``/``pks``/``page``
    so the inherited v3 logic continues to see its expected inputs.
    """

    renderer_classes = (EnvelopeJSONRenderer,)
    requires_page = False

    if TYPE_CHECKING:
        kwargs: dict  # pyright: ignore[reportUninitializedInstanceVariable]

    def initial(self, request: "Request", *args, **kwargs):
        """Rewrite self.kwargs before DRF's per-request setup runs."""
        self._translate_kwargs(request)
        super().initial(request, *args, **kwargs)  # pyright: ignore[reportAttributeAccessIssue]

    def _translate_kwargs(self, request: "Request") -> None:
        """
        In-place rewrite of ``self.kwargs`` from v4 → v3 shape.

        The collection segment names the v4 caller's *current* nav
        level (matching v3's single-char ``group`` kwarg); ``pks``
        comes from the optional ``parentIds`` segment. v3's
        ``model_group`` advances to the next-visible level per the
        user's ``show`` settings — same behavior as v3.

        Special case: ``/browse/publishers`` (no parent ids) maps to
        v3's ``ROOT_GROUP`` ('r') instead of 'p' so the response
        lists publisher rows themselves rather than their next-visible
        children. v3's ``r`` group was reserved for that "list the
        publishers" semantics; v4 drops the magic letter but keeps
        the behavior at the root URL.
        """
        kwargs = self.kwargs
        collection = kwargs.pop("collection", None)
        parent_ids = kwargs.pop("parent_ids", None)
        if collection is not None:
            if collection == "publishers" and parent_ids is None:
                kwargs["group"] = "r"
            else:
                kwargs["group"] = COLLECTION_TO_GROUP[collection]
        if parent_ids is None:
            kwargs["pks"] = ()
        else:
            kwargs["pks"] = tuple(parent_ids)
        if self.requires_page and "page" not in kwargs:
            try:
                kwargs["page"] = int(request.GET.get("page", 1))
            except (TypeError, ValueError):
                kwargs["page"] = 1


class V4BrowseView(_V4BrowseTranslateMixin, BrowserView):
    """
    ``GET /api/v4/browse/{collection}[/{parentIds}]``.

    Card or table mode is selected by ``view_mode`` on the user's
    settings row (or the ``?view_mode=`` override) — same behavior as
    v3. Page number comes from ``?page=`` (v3 had it in the path).

    The v4 serializer (:class:`V4BrowserPageSerializer`) strips the
    off-mode fields from the response so card requests skip ``rows``
    and table requests skip ``groups`` / ``books``.
    """

    requires_page = True

    @override
    def get_serializer_class(self):
        """Defer the v4 import; matches the metadata view pattern."""
        from codex.serializers.v4.browse import V4BrowserPageSerializer

        return V4BrowserPageSerializer


class V4BrowseChoicesView(_V4BrowseTranslateMixin, BrowserChoicesAvailableView):
    """``GET /api/v4/browse/{collection}[/{parentIds}]/choices``."""


class V4BrowseChoicesFieldView(_V4BrowseTranslateMixin, BrowserChoicesView):
    """
    ``GET /api/v4/browse/{collection}[/{parentIds}]/choices/{field}``.

    ``field`` is forwarded as ``field_name`` (v3 kwarg) by the URL pattern.
    """


class V4BrowseMetadataView(_V4BrowseTranslateMixin, MetadataView):
    """
    ``GET /api/v4/browse/{collection}[/{parentIds}]/metadata``.

    Uses the v4 metadata serializer so credits ship role-pivoted
    (``{role: [persons]}``) and identifiers ship parsed
    (``{type, code, displayName, pk, url}``) — see Phase 5 in
    ``tasks/api-v4.md``.
    """

    serializer_class = None  # set below to avoid forward-ref cycles

    @override
    def get_serializer_class(self):
        """Defer the import to runtime — the serializer pulls in comicbox."""
        from codex.serializers.v4.metadata import V4MetadataSerializer

        return V4MetadataSerializer


class V4BrowseDownloadView(_V4BrowseTranslateMixin, GroupDownloadView):
    """``GET /api/v4/browse/{collection}/{parentIds}/download/{filename}``."""


class V4BrowseImportView(_V4BrowseTranslateMixin, LazyImportView):
    """``POST /api/v4/browse/{collection}/{parentIds}/import``."""


class V4BrowseRefreshView(_V4BrowseTranslateMixin, ForceUpdateView):
    """``POST /api/v4/browse/{collection}/{parentIds}/refresh``."""


class V4BrowseBookmarkView(_V4BrowseTranslateMixin, BookmarkView):
    """``PATCH /api/v4/browse/{collection}/{parentIds}/bookmark`` (bulk)."""


class V4BrowseSettingsView(_V4BrowseTranslateMixin, BrowserSettingsView):
    """``GET|PATCH|DELETE /api/v4/browse/{collection}/settings``."""


class V4BrowseSavedSettingsListView(
    _V4BrowseTranslateMixin, SavedBrowserSettingsListView
):
    """``GET|POST /api/v4/browse/{collection}/saved-settings``."""


class V4BrowseSavedSettingsDetailView(
    _V4BrowseTranslateMixin, SavedBrowserSettingsLoadView
):
    """``GET|DELETE /api/v4/browse/{collection}/saved-settings/{id}``."""

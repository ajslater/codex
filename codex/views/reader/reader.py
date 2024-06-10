"""Views for reading comic books."""

from copy import deepcopy
from types import MappingProxyType

from comicbox.box import Comicbox
from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.librarian.importer.tasks import LazyImportComicsTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.serializers.reader import (
    ReaderComicsSerializer,
    ReaderViewInputSerializer,
)
from codex.serializers.redirect import ReaderRedirectSerializer
from codex.views.const import FOLDER_GROUP, STORY_ARC_GROUP
from codex.views.reader.arcs import ReaderArcsView
from codex.views.util import pop_name, reparse_json_query_params

LOG = get_logger(__name__)
_VALID_ARC_GROUPS = frozenset({"f", "s", "a"})
_JSON_KEYS = frozenset({"arc", "breadcrumbs"})
_BROWSER_SESSION_DEFAULTS = ReaderArcsView.SESSION_DEFAULTS[
    ReaderArcsView.BROWSER_SESSION_KEY
]
_DEFAULT_PARAMS = {
    "breadcrumbs": _BROWSER_SESSION_DEFAULTS["breadcrumbs"],
    "show": _BROWSER_SESSION_DEFAULTS["show"],
    "top_group": _BROWSER_SESSION_DEFAULTS["top_group"],
}


class ReaderView(
    ReaderArcsView,
):
    """Get info for displaying comic pages."""

    serializer_class = ReaderComicsSerializer
    input_serializer_class = ReaderViewInputSerializer

    SESSION_KEY = "reader"
    TARGET = "reader"

    def __init__(self, *args, **kwargs):
        """Initialize instance vars."""
        super().__init__(*args, **kwargs)
        self.series_pks: tuple[int, ...] = ()

    def _raise_not_found(self):
        """Raise not found exception."""
        pk = self.kwargs.get("pk")
        detail = {
            "route": reverse("app:start"),
            "reason": f"comic {pk} not found",
            "serializer": ReaderRedirectSerializer,
        }
        raise NotFound(detail=detail)

    def _ensure_arc(self, params):
        """arc.group validation."""
        # Can't be in the serializer
        arc = params.get("arc", {})
        if arc.get("group") not in _VALID_ARC_GROUPS:
            top_group = params["top_group"]
            if top_group in (FOLDER_GROUP, STORY_ARC_GROUP):
                arc["group"] = top_group
            else:
                arc["group"] = "s"
                breadcrumbs = params["breadcrumbs"]
                series_pks = self.get_series_pks_from_breadcrumbs(breadcrumbs)
                if series_pks:
                    arc["pks"] = series_pks

        params["arc"] = arc

    def _parse_params(self):
        data = self.request.GET
        data = reparse_json_query_params(self.request.GET, _JSON_KEYS)
        serializer = self.input_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)

        params = deepcopy(_DEFAULT_PARAMS)
        if serializer.validated_data:
            params.update(serializer.validated_data)  # type: ignore
        self._ensure_arc(params)

        self.params = MappingProxyType(params)

    @staticmethod
    def _lazy_metadata(current, prev_book, next_book):
        """Get reader metadata from comicbox if it's not in the db."""
        import_pks = set()
        if current and not (current.page_count and current.file_type):
            with Comicbox(current.path) as cb:
                current.file_type = cb.get_file_type()
                current.page_count = cb.get_page_count()
            import_pks.add(current.pk)

        if prev_book and not prev_book.page_count:
            with Comicbox(prev_book.path) as cb:
                prev_book.page_count = cb.get_page_count()
            import_pks.add(prev_book.pk)

        if next_book and not next_book.page_count:
            with Comicbox(next_book.path) as cb:
                next_book.page_count = cb.get_page_count()
            import_pks.add(next_book.pk)

        if import_pks:
            task = LazyImportComicsTask(frozenset(import_pks))
            LIBRARIAN_QUEUE.put(task)

    def get_object(self):
        """Get the previous and next comics in a group or story arc."""
        # Books
        books = self.get_book_collection()

        current = books.get("current")
        if not current:
            self._raise_not_found()

        prev_book = books.get("prev")
        next_book = books.get("next")
        self._lazy_metadata(current, prev_book, next_book)

        books = {
            "current": current,
            "prev_book": prev_book,
            "next_book": next_book,
        }

        # Arcs
        arcs, mtime = self.get_arcs(current)

        arc = self.params.get("arc", {})
        if not arc.get("group"):
            arc["group"] = current.arc_group  # type: ignore
        if not arc.get("pks"):
            arc["pks"] = (current.arc_pk,)  # type: ignore
        arc["index"] = current.arc_index  # type:ignore
        arc["count"] = current.arc_count  # type: ignore

        close_route = self.get_last_route()
        close_route = pop_name(close_route)

        return {
            "books": books,
            "arcs": arcs,
            "arc": arc,
            "close_route": close_route,
            "mtime": mtime,
        }

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "arc[group]", OpenApiTypes.STR, enum=sorted(_VALID_ARC_GROUPS)
            ),
            OpenApiParameter("arc[pks]", OpenApiTypes.STR),
        ]
    )
    def get(self, *args, **kwargs):
        """Get the book info."""
        self._parse_params()
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

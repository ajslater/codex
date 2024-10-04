"""Views for reading comic books."""

from comicbox.box import Comicbox
from django.urls import reverse
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.librarian.importer.tasks import LazyImportComicsTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.serializers.reader import ReaderComicsSerializer, ReaderViewInputSerializer
from codex.serializers.redirect import ReaderRedirectSerializer
from codex.views.reader.arcs import ReaderArcsView

LOG = get_logger(__name__)


class ReaderView(ReaderArcsView):
    """Get info for displaying comic pages."""

    serializer_class = ReaderComicsSerializer

    SESSION_KEY = "reader"
    TARGET = "reader"

    def _raise_not_found(self):
        """Raise not found exception."""
        pk = self.kwargs.get("pk")
        detail = {
            "route": reverse("app:start"),
            "reason": f"comic {pk} not found",
            "serializer": ReaderRedirectSerializer,
        }
        raise NotFound(detail=detail)

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

    def get_object(self):  # type: ignore
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

        return {
            "books": books,
            "arcs": arcs,
            "arc": arc,
            "close_route": close_route,
            "mtime": mtime,
        }

    @extend_schema(parameters=[ReaderViewInputSerializer])
    def get(self, *args, **kwargs):
        """Get the book info."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

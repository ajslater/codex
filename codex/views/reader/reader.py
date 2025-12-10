"""Views for reading comic books."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from typing_extensions import override

from codex.serializers.reader import ReaderComicsSerializer, ReaderViewInputSerializer
from codex.views.reader.books import ReaderBooksView


class ReaderView(ReaderBooksView):
    """Get info for displaying comic pages."""

    serializer_class: type[BaseSerializer] | None = ReaderComicsSerializer

    SESSION_KEY: str = "reader"
    TARGET: str = "reader"

    @override
    def get_object(self):
        """Get the previous and next comics in a group or story arc."""
        # get_arcs & get_book_collection populates those arc self valirables.
        # So order is important.
        arcs, mtime = self.get_arcs()
        books = self.get_book_collection()
        arc = {
            "group": self._selected_arc_group,
            "ids": self._selected_arc_ids,
            "index": self._selected_arc_index,
            "count": self._selected_arc_count,
        }
        close_route = self.get_last_route()

        return {
            "arc": arc,
            "arcs": arcs,
            "books": books,
            "close_route": close_route,
            "mtime": mtime,
        }

    @extend_schema(parameters=[ReaderViewInputSerializer])
    def get(self, *args, **kwargs):
        """Get the book info."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

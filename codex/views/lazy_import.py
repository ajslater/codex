"""Lazy metadata-import view."""

from rest_framework.response import Response

from codex.collection import Collection
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.tasks import LazyImportComicsTask
from codex.serializers.mixins import OKSerializer
from codex.views.auth import AuthGenericAPIView

# Browse collections that resolve to a set of comics for lazy metadata import.
_LAZY_IMPORT_COLLECTIONS = frozenset({Collection.COMIC, Collection.FOLDER})


class LazyImportView(AuthGenericAPIView):
    """Queue a lazy metadata import for the comics under a browse collection."""

    serializer_class = OKSerializer

    def post(self, *args, **kwargs) -> Response:
        """Enqueue a lazy-import task for a comics / folders collection."""
        collection = self.kwargs.get("collection", "")
        if collection in _LAZY_IMPORT_COLLECTIONS:
            pks = self.kwargs.get("pks", ())
            pks = frozenset(pks)
            LIBRARIAN_QUEUE.put(LazyImportComicsTask(collection=collection, pks=pks))
        serializer = self.get_serializer()
        return Response(serializer.data)

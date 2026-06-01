"""Lazy metadata-import view."""

from rest_framework.response import Response

from codex.group import Group
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.tasks import LazyImportComicsTask
from codex.serializers.mixins import OKSerializer
from codex.views.auth import AuthGenericAPIView

# Browse groups that resolve to a set of comics for lazy metadata import.
_LAZY_IMPORT_GROUPS = frozenset({Group.COMIC, Group.FOLDER})


class LazyImportView(AuthGenericAPIView):
    """Queue a lazy metadata import for the comics under a browse group."""

    serializer_class = OKSerializer

    def post(self, *args, **kwargs) -> Response:
        """Enqueue a lazy-import task for a comics / folders group."""
        group = self.kwargs.get("group", "")
        if group in _LAZY_IMPORT_GROUPS:
            pks = self.kwargs.get("pks", ())
            pks = frozenset(pks)
            LIBRARIAN_QUEUE.put(LazyImportComicsTask(group=group, pks=pks))
        serializer = self.get_serializer()
        return Response(serializer.data)

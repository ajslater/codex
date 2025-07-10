"""Version View."""

from rest_framework.response import Response

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.tasks import LazyImportComicsTask
from codex.serializers.mixins import OKSerializer
from codex.views.auth import AuthGenericAPIView


class LazyImportView(AuthGenericAPIView):
    """Return Codex Versions."""

    serializer_class = OKSerializer

    def get(self, *args, **kwargs):
        """Get Versions."""
        group = self.kwargs.get("group", "")
        if group in "fc":
            pks = self.kwargs.get("pks", ())
            pks = frozenset(pks)
            LIBRARIAN_QUEUE.put(LazyImportComicsTask(group=group, pks=pks))
        serializer = self.get_serializer()
        return Response(serializer.data)

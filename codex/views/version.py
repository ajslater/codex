"""Version View."""

from rest_framework.response import Response
from typing_extensions import override

from codex.librarian.bookmark.tasks import CodexLatestVersionTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models import Timestamp
from codex.serializers.versions import VersionsSerializer
from codex.version import VERSION
from codex.views.auth import AuthGenericAPIView


class VersionView(AuthGenericAPIView):
    """Return Codex Versions."""

    serializer_class = VersionsSerializer

    @override
    def get_object(self) -> dict[str, str]:
        """Get the versions."""
        ts = Timestamp.objects.get(key=Timestamp.Choices.CODEX_VERSION.value)
        if ts.version:
            latest_version = ts.version
        else:
            LIBRARIAN_QUEUE.put(CodexLatestVersionTask())
            latest_version = "fetching..."
        return {"installed": VERSION, "latest": latest_version}

    def get(self, *args, **kwargs):
        """Get Versions."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

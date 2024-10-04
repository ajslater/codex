"""Version View."""

from rest_framework.response import Response

from codex.librarian.janitor.tasks import JanitorLatestVersionTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models import Timestamp
from codex.serializers.versions import VersionsSerializer
from codex.version import VERSION
from codex.views.auth import AuthGenericAPIView


class VersionView(AuthGenericAPIView):
    """Return Codex Versions."""

    serializer_class = VersionsSerializer

    def get_object(self) -> dict[str, str]:  # type: ignore
        """Get the versions."""
        ts = Timestamp.objects.get(key=Timestamp.TimestampChoices.CODEX_VERSION.value)
        if ts.version:
            latest_version = ts.version
        else:
            LIBRARIAN_QUEUE.put(JanitorLatestVersionTask())
            latest_version = "fetching..."
        return {"installed": VERSION, "latest": latest_version}

    def get(self, *args, **kwargs):
        """Get Versions."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

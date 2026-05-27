"""v4 version endpoint — smoke test for the scaffold."""

from typing import override

from rest_framework.response import Response

from codex.librarian.bookmark.tasks import CodexLatestVersionTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models import Timestamp
from codex.serializers.v4.version import VersionEnvelopeSerializer
from codex.settings import DOCKER_IMAGE_DEPRECATED
from codex.version import VERSION
from codex.views.v4.common import V4GenericAPIView, envelope


class V4VersionView(V4GenericAPIView):
    """v4 ``/version`` — same payload as v3 wrapped in the envelope."""

    serializer_class = VersionEnvelopeSerializer

    @override
    def get_object(self) -> dict[str, str]:
        """Build the version payload (mirrors v3 ``VersionView``)."""
        ts = Timestamp.objects.get(key=Timestamp.Choices.CODEX_VERSION.value)
        if ts.value:
            latest_version = ts.value
        else:
            LIBRARIAN_QUEUE.put(CodexLatestVersionTask())
            latest_version = "fetching..."
        return {
            "installed": VERSION,
            "latest": latest_version,
            "warning": DOCKER_IMAGE_DEPRECATED,
        }

    def get(self, *args, **kwargs) -> Response:
        """GET /api/v4/version."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(envelope(serializer.data))

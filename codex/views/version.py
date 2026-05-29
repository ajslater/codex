"""Version View."""

from typing import override

from rest_framework.response import Response

from codex.librarian.bookmark.tasks import CodexLatestVersionTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models import Timestamp
from codex.serializers.versions import VersionsSerializer
from codex.settings import DOCKER_IMAGE_DEPRECATED
from codex.version import VERSION
from codex.views.auth import AuthGenericAPIView


def version_payload() -> dict[str, str]:
    """
    Build the ``{installed, latest, warning}`` version dict.

    Shared by :class:`VersionView` and the composite
    :class:`~codex.views.session.SessionView` so the two endpoints
    can't drift. Kicks off a latest-version fetch task when the cached
    ``Timestamp`` row is still empty.
    """
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


class VersionView(AuthGenericAPIView):
    """Return Codex Versions."""

    serializer_class = VersionsSerializer

    @override
    def get_object(self) -> dict[str, str]:
        """Get the versions."""
        return version_payload()

    def get(self, *args, **kwargs) -> Response:
        """Get Versions."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

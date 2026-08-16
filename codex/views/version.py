"""Version View."""

from typing import override

from rest_framework.response import Response

from codex.librarian.bookmark.tasks import CodexLatestVersionTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models import Timestamp
from codex.serializers.versions import VersionsSerializer
from codex.settings import DOCKER_IMAGE_DEPRECATED
from codex.util import is_docker
from codex.version import VERSION, is_outdated
from codex.views.auth import AuthGenericAPIView


def version_payload() -> dict[str, str | bool]:
    """
    Build the ``{installed, latest, outdated, docker, warning}`` version dict.

    Shared by :class:`VersionView` and the composite
    :class:`~codex.views.session.SessionView` so the two endpoints
    can't drift. Kicks off a latest-version fetch task when the cached
    ``Timestamp`` row is still empty.

    ``outdated`` is computed here rather than in the browser so version
    comparison happens once, in the one place that already knows how to
    read a PEP 440 version. ``docker`` tells the browser that codex
    cannot install over itself here, so an upgrade means pulling a new
    image rather than running the update job.
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
        "outdated": is_outdated(VERSION, ts.value),
        "docker": is_docker(),
        "warning": DOCKER_IMAGE_DEPRECATED,
    }


class VersionView(AuthGenericAPIView):
    """Return Codex Versions."""

    serializer_class = VersionsSerializer

    @override
    def get_object(self) -> dict[str, str | bool]:
        """Get the versions."""
        return version_payload()

    def get(self, *args, **kwargs) -> Response:
        """Get Versions."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

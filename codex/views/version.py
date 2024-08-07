"""Version View."""

from rest_framework.response import Response

from codex.serializers.versions import VersionsSerializer
from codex.version import PACKAGE_NAME, VERSION, get_latest_version
from codex.views.auth import AuthGenericAPIView


class VersionView(AuthGenericAPIView):
    """Return Codex Versions."""

    serializer_class = VersionsSerializer

    def get_object(self):
        """Get the versions."""
        latest_version = get_latest_version(PACKAGE_NAME)
        return {"installed": VERSION, "latest": latest_version}

    def get(self, *args, **kwargs):
        """Get Versions."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

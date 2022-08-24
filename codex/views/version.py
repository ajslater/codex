"""Version View."""
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from codex.serializers.versions import VersionsSerializer
from codex.version import PACKAGE_NAME, VERSION, get_latest_version


class VersionView(GenericAPIView):
    """Return Codex Versions."""

    serializer_class = VersionsSerializer

    def get_object(self):
        """Get the versions."""
        latest_version = get_latest_version(PACKAGE_NAME)
        obj = {"installed": VERSION, "latest": latest_version}
        return obj

    def get(self, request, *args, **kwargs):
        """Get Versions."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

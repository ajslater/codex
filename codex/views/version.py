"""Version View."""
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.serializers.browser import VersionsSerializer
from codex.version import PACKAGE_NAME, VERSION, get_latest_version


class VersionView(APIView):
    """Return Codex Versions."""

    def get(self, request, *args, **kwargs):
        """Get the versions."""
        latest_version = get_latest_version(PACKAGE_NAME)
        data = {"installed": VERSION, "latest": latest_version}
        serializer = VersionsSerializer(data)
        return Response(serializer.data)

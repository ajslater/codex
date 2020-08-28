import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from codex.models import Library
from codex.serializers.browse import ScanNotifySerializer


LOG = logging.getLogger(__name__)


class ScanNotifyView(APIView):
    """API endpoint for the scan notifier."""

    def get(self, request, *args, **kwargs):
        """Return if any libraries are scanning."""
        any_in_progress = Library.objects.filter(scan_in_progress=True).exists()
        serializer = ScanNotifySerializer({"scanInProgress": any_in_progress})
        return Response(serializer.data)

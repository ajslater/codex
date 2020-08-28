import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from codex.librarian.queue import QUEUE
from codex.models import Library
from codex.serializers.browse import ScanNotifySerializer


LOG = logging.getLogger(__name__)


class ScanNotifyView(APIView):
    """API endpoint for the scan notifier."""

    def get(self, request, *args, **kwargs):
        """Return if any libraries are scanning."""
        any_in_progress = Library.objects.filter(scan_in_progress=True).exists()
        print(f"{any_in_progress=} QUEUE.empty():{QUEUE.empty()}")
        any_in_progress |= not QUEUE.empty()
        serializer = ScanNotifySerializer({"scanInProgress": any_in_progress})
        return Response(serializer.data)

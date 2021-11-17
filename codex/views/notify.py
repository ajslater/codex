"""Notify views."""
from logging import getLogger

from django.views.decorators.cache import cache_control
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.models import Library
from codex.serializers.notify import ScanNotifySerializer
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers


LOG = getLogger(__name__)
MIN_SCAN_WAIT = 5


class ScanNotifyView(APIView):
    """API endpoint for the scan notifier."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    @cache_control(max_age=MIN_SCAN_WAIT)
    def get(self, request, *args, **kwargs):
        """Return if any libraries are scanning."""
        any_in_progress = Library.objects.filter(update_in_progress=True).exists()
        any_in_progress |= not LIBRARIAN_QUEUE.empty()
        data = {"scanInProgress": any_in_progress}
        serializer = ScanNotifySerializer(data)
        return Response(serializer.data)

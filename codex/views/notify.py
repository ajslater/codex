"""Notify views."""
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.models import Library
from codex.serializers.notify import NotifySerializer
from codex.settings.logging import get_logger
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers


LOG = get_logger(__name__)


class NotifyView(APIView):
    """API endpoint for the notifier status."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    def get(self, request, *args, **kwargs):
        """Return if any libraries are updating."""
        any_in_progress = Library.objects.filter(update_in_progress=True).exists()
        any_in_progress |= not LIBRARIAN_QUEUE.empty()
        data = {"update_in_progress": any_in_progress}
        serializer = NotifySerializer(data)
        return Response(serializer.data)

"""Poll all libraries."""

from rest_framework.response import Response
from rest_framework.views import APIView

from codex.admin import AdminLibrary
from codex.models import Library
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers


class PollView(APIView):
    """Return the comic archive file as an attachment."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    def post(self, request, *args, **kwargs):
        """Download a comic archive."""
        queryset = Library.objects.all()
        AdminLibrary.queue_poll(queryset, False)
        return Response()

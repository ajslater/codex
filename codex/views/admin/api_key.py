"""API Key Endpoint."""
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from codex.models import Timestamp


class AdminAPIKey(GenericAPIView):
    """Regenerate API Key."""

    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        """Regenerate the API Key."""
        ts = Timestamp.objects.get(name=Timestamp.API_KEY)
        ts.save_uuid_version()
        # probably should respond with the new key and make this a get.
        return Response()

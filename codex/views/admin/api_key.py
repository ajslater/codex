"""API Key Endpoint."""
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from codex.models import Timestamp
from codex.serializers.admin import APIKeySerializer


class AdminAPIKey(GenericAPIView):
    """Regenerate API Key."""

    permission_classes = [IsAdminUser]
    serializer_class = APIKeySerializer
    input_serializer_class = None

    @extend_schema(request=input_serializer_class)
    def post(self, *args, **kwargs):
        """Regenerate the API Key."""
        ts = Timestamp.objects.get(key=Timestamp.TimestampChoices.API_KEY.value)
        ts.save_uuid_version()
        serializer = self.get_serializer(ts)
        return Response(serializer.data)

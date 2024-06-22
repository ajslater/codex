"""API Key Endpoint."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.models import Timestamp
from codex.serializers.admin.stats import APIKeySerializer
from codex.views.admin.auth import AdminGenericAPIView


class AdminAPIKey(AdminGenericAPIView):
    """Regenerate API Key."""

    serializer_class = APIKeySerializer
    input_serializer_class = None

    @extend_schema(
        # parameters=[input_serializer_class],
        request=input_serializer_class
    )
    def put(self, *_args, **_kwargs):
        """Regenerate the API Key."""
        ts = Timestamp.objects.get(key=Timestamp.TimestampChoices.API_KEY.value)
        ts.save_uuid_version()
        serializer = self.get_serializer(ts)
        return Response(serializer.data)

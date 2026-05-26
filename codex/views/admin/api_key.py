"""API Key Endpoint."""

import base64
import uuid

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag
from codex.serializers.admin.stats import APIKeySerializer
from codex.views.admin.auth import AdminGenericAPIView


def _new_api_key() -> str:
    """Generate a fresh URL-safe base64 UUID string."""
    uuid_bytes = uuid.uuid4().bytes
    b64_bytes = base64.urlsafe_b64encode(uuid_bytes)
    return b64_bytes.decode("utf-8").replace("=", "")


class AdminAPIKey(AdminGenericAPIView):
    """Read or regenerate the API Key."""

    serializer_class = APIKeySerializer
    input_serializer_class = None

    def get(self, *_args, **_kwargs) -> Response:
        """Return the current API Key."""
        flag = AdminFlag.objects.get(key=AdminFlagChoices.API_KEY.value)
        serializer = self.get_serializer(flag)
        return Response(serializer.data)

    @extend_schema(request=input_serializer_class)
    def put(self, *_args, **_kwargs) -> Response:
        """Regenerate the API Key."""
        flag = AdminFlag.objects.get(key=AdminFlagChoices.API_KEY.value)
        flag.value = _new_api_key()
        flag.save()
        serializer = self.get_serializer(flag)
        return Response(serializer.data)

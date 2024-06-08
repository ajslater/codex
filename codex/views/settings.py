"""Settings View."""

from abc import ABC

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.serializers.settings import SettingsSerializer
from codex.views.session import SessionView
from codex.views.util import reparse_json_query_params

_JSON_PARAMS = frozenset({"only"})


class SettingsView(SessionView, ABC):
    """Settings View."""

    input_serializer_class = SettingsSerializer

    def get(self, *args, **kwargs):
        """Get session settings."""
        data = self.request.GET
        data = reparse_json_query_params(data, _JSON_PARAMS)
        serializer = self.input_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        only = serializer.validated_data.get("only")  # type: ignore
        params = self.load_params_from_session(only=only)
        serializer = self.get_serializer(params)
        return Response(serializer.data)

    @extend_schema(responses=None)
    def patch(self, *args, **kwargs):
        """Update session settings."""
        data = self.request.data  # type: ignore
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.save_params_to_session(serializer.validated_data)
        return Response()

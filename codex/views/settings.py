"""Settings View."""

from abc import ABC

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.serializers.settings import SettingsSerializer
from codex.views.session import SessionView
from codex.views.util import reparse_json_query_params

_GET_JSON_PARAMS = frozenset({"only"})


class SettingsView(SessionView, ABC):
    """Settings View."""

    input_serializer_class = SettingsSerializer

    def validate_settings_get(self, _validated_data, params: dict) -> dict:
        """Change bad settings."""
        return params

    @extend_schema(parameters=[SettingsSerializer])
    def get(self, *args, **kwargs):
        """Get session settings."""
        data = self.request.GET
        data = reparse_json_query_params(data, _GET_JSON_PARAMS)
        serializer = self.input_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        only = validated_data.get("only") if validated_data else None  # type: ignore
        params = self.load_params_from_session(only=only)
        params = self.validate_settings_get(validated_data, params)
        serializer = self.get_serializer(params)
        return Response(serializer.data)

    @extend_schema(responses=None)
    def patch(self, *args, **kwargs):
        """Update session settings."""
        data = self.request.data  # type: ignore
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        params = self.load_params_from_session()
        params.update(serializer.validated_data)
        self.save_params_to_session(params)
        return Response()

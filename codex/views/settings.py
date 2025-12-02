"""Settings View."""

from abc import ABC

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.serializers.settings import SettingsInputSerializer
from codex.views.session import SessionView


class SettingsView(SessionView, ABC):
    """Settings View."""

    input_serializer_class: type[SettingsInputSerializer] = SettingsInputSerializer

    def validate_settings_get(self, validated_data, params: dict) -> dict:  # noqa: ARG002
        """Change bad settings."""
        return params

    @extend_schema(parameters=[SettingsInputSerializer])
    def get(self, *args, **kwargs):
        """Get session settings."""
        serializer = self.input_serializer_class(data=self.request.GET)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        only = validated_data.get("only") if validated_data else None
        params = self.load_params_from_session(only=only)
        params = self.validate_settings_get(validated_data, params)
        serializer = self.get_serializer(params)
        return Response(serializer.data)

    @extend_schema(responses=None)
    def patch(self, *args, **kwargs):
        """Update session settings."""
        data = self.request.data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        # Reader has arc validation, but not really
        params = self.load_params_from_session()
        params.update(serializer.validated_data)
        self.save_params_to_session(params)
        serializer = self.get_serializer(params)
        return Response(serializer.data)

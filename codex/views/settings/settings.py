"""Settings View."""

from abc import ABC

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.serializers.settings import SettingsInputSerializer
from codex.views.settings.base import SettingsWriteView
from codex.views.settings.const import NULL_VALUES


class SettingsView(SettingsWriteView, ABC):
    """Settings View."""

    input_serializer_class: type[SettingsInputSerializer] = SettingsInputSerializer

    # When True, null and empty values are stripped from PATCH data
    # so that existing settings are never blanked out.
    REJECT_NULL_UPDATES: bool = False

    def validate_settings_get(self, validated_data, params: dict) -> dict:  # noqa: ARG002
        """Change bad settings."""
        return params

    @extend_schema(parameters=[SettingsInputSerializer])
    def get(self, *args, **kwargs) -> Response:
        """Get session settings."""
        serializer = self.input_serializer_class(data=self.request.GET)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        only = validated_data.get("only") if validated_data else None
        params = self.load_params_from_settings(only=only)
        params = self.validate_settings_get(validated_data, params)
        serializer = self.get_serializer(params)
        return Response(serializer.data)

    @extend_schema(responses=None)
    def patch(self, *args, **kwargs) -> Response:
        """Update session settings."""
        data = self.request.data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        updates = serializer.validated_data
        if self.REJECT_NULL_UPDATES:
            updates = {k: v for k, v in updates.items() if v not in NULL_VALUES}
        params = self.load_params_from_settings()
        params.update(updates)
        self.save_params_to_settings(params)
        serializer = self.get_serializer(params)
        return Response(serializer.data)

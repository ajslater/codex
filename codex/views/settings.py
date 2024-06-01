"""Settings View."""

from abc import ABC

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.views.session import SessionView


class SettingsView(SessionView, ABC):
    """Settings View."""

    def get(self, *args, **kwargs):
        """Get session settings."""
        defaults = self.SESSION_DEFAULTS[self.SESSION_KEY]
        session = self.request.session.get(self.SESSION_KEY, defaults)
        params = self._get_source_values_or_set_defaults(defaults, session, {})
        data = {}
        for key, filter_name in params.get("filters", {}).items():
            if filter_name:
                data[key] = filter_name
        params["filters"] = data
        serializer = self.get_serializer(params)
        return Response(serializer.data)

    @extend_schema(responses=None)
    def put(self, *args, **kwargs):
        """Update session settings."""
        data = self.request.data  # type: ignore
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.save_params_to_session(serializer.validated_data)
        return Response()

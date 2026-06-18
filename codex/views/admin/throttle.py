"""Admin Throttle Settings View."""

from rest_framework.response import Response

from codex.models import ThrottleSettings
from codex.serializers.admin.throttle import ThrottleSettingsSerializer
from codex.views.admin.auth import AdminAPIView


class AdminThrottleSettingsView(AdminAPIView):
    """GET/PUT for the ThrottleSettings singleton."""

    def get(self, _request):
        """Return the current throttle settings."""
        row = ThrottleSettings.objects.get(pk=1)
        serializer = ThrottleSettingsSerializer(row)
        return Response(serializer.data)

    def put(self, request):
        """Update throttle settings; DB-aware throttle classes pick up changes."""
        row = ThrottleSettings.objects.get(pk=1)
        serializer = ThrottleSettingsSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ThrottleSettingsSerializer(row).data)

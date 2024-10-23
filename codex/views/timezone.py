"""Set timezone from browser endpoint."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.serializers.auth import TimezoneSerializer
from codex.serializers.mixins import OKSerializer
from codex.views.auth import AuthGenericAPIView

LOG = get_logger(__name__)


class TimezoneView(AuthGenericAPIView):
    """User info."""

    input_serializer_class = TimezoneSerializer
    serializer_class = OKSerializer

    def _save_timezone(self, django_timezone):
        """Save django timezone in session."""
        if not django_timezone:
            return
        session = self.request.session
        session["django_timezone"] = django_timezone
        session.save()

    @extend_schema(request=input_serializer_class)
    def put(self, *args, **kwargs):
        """Get the user info for the current user."""
        data = self.request.data
        serializer = self.input_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            timezone = serializer.validated_data.get("timezone")
            self._save_timezone(timezone)
        except Exception as exc:
            reason = f"update user timezone {exc}"
            LOG.warning(reason)

        serializer = self.get_serializer()
        return Response(serializer.data)

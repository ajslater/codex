"""Admin Stats View."""

from typing import ClassVar

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import empty

from codex.librarian.telemeter.stats import CodexStats
from codex.logger.logging import get_logger
from codex.models.admin import Timestamp
from codex.permissions import HasAPIKeyOrIsAdminUser
from codex.serializers.admin.stats import (
    AdminStatsRequestSerializer,
    StatsSerializer,
)
from codex.views.admin.auth import AdminGenericAPIView

LOG = get_logger(__name__)


class AdminStatsView(AdminGenericAPIView):
    """Admin Flag Viewset."""

    permission_classes: ClassVar[list] = [HasAPIKeyOrIsAdminUser]  # type: ignore
    serializer_class = StatsSerializer
    input_serializer_class = AdminStatsRequestSerializer

    def _parse_params(self):
        """Parse and input params."""
        data = self.request.GET

        input_serializer = self.input_serializer_class(data=data)
        input_serializer.is_valid(raise_exception=True)
        params = {}
        if input_serializer.validated_data and not isinstance(
            input_serializer.validated_data, empty
        ):
            for key, value in input_serializer.validated_data.items():
                if value:
                    params[key] = value
        return params

    def _add_api_key(self, obj):
        """Add the api key to the config object if specified."""
        request_counts = self.params.get("config", {})
        if request_counts and ("apikey" not in request_counts):
            return
        api_key = Timestamp.objects.get(
            key=Timestamp.TimestampChoices.API_KEY.value
        ).version
        if "config" not in obj:
            obj["config"] = {}
        obj["config"]["api_key"] = api_key

    def get_object(self):
        """Get the stats object with an api key."""
        getter = CodexStats(self.params)
        obj = getter.get()
        self._add_api_key(obj)
        return obj

    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Get the stats object and serialize it."""
        self.params = self._parse_params()
        obj = self.get_object()

        serializer = self.get_serializer(obj)
        return Response(serializer.data)

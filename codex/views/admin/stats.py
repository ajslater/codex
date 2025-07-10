"""Admin Stats View."""

from types import MappingProxyType
from typing import Any, ClassVar

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.serializers import empty
from typing_extensions import override

from codex.librarian.telemeter.stats import CodexStats
from codex.models.admin import Timestamp
from codex.serializers.admin.stats import (
    AdminStatsRequestSerializer,
    StatsSerializer,
)
from codex.views.admin.auth import AdminGenericAPIView
from codex.views.admin.permissions import HasAPIKeyOrIsAdminUser


class AdminStatsView(AdminGenericAPIView):
    """Admin Flag Viewset."""

    permission_classes: ClassVar[list[type[BasePermission]]] = [HasAPIKeyOrIsAdminUser]
    serializer_class = StatsSerializer
    input_serializer_class = AdminStatsRequestSerializer

    def __init__(self, *args, **kwargs):
        """Initialize properties."""
        super().__init__(*args, **kwargs)
        self._params: MappingProxyType[str, Any] | None = None

    @property
    def params(self) -> MappingProxyType[str, Any]:
        """Parse and input params."""
        if self._params is None:
            data = self.request.GET

            input_serializer = self.input_serializer_class(data=data)
            input_serializer.is_valid(raise_exception=True)
            self._params = MappingProxyType(
                {
                    key: value
                    for key, value in input_serializer.validated_data.items()
                    if input_serializer.validated_data
                    and not isinstance(input_serializer.validated_data, empty)
                }
            )
        return self._params

    def _add_api_key(self, obj):
        """Add the api key to the config object if specified."""
        request_counts = self.params.get("config", {})
        if request_counts and ("apikey" not in request_counts):
            return
        api_key = Timestamp.objects.get(key=Timestamp.Choices.API_KEY.value).version
        if "config" not in obj:
            obj["config"] = {}
        obj["config"]["api_key"] = api_key

    @override
    def get_object(self):
        """Get the stats object with an api key."""
        getter = CodexStats(self.params)
        obj = getter.get()
        self._add_api_key(obj)
        return obj

    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Get the stats object and serialize it."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

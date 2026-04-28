"""Admin Stats View."""

import hashlib
import json
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Final, override

from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import empty

from codex.librarian.telemeter.stats import CodexStats
from codex.models.admin import Timestamp
from codex.serializers.admin.stats import (
    AdminStatsRequestSerializer,
    StatsSerializer,
)
from codex.views.admin.auth import AdminGenericAPIView
from codex.views.admin.permissions import HasAPIKeyOrIsAdminUser

# Cache TTL for the assembled stats object. The data underneath only
# changes as the librarian imports / users sign up — a brief staleness
# window beats the ~30 ``COUNT(*)`` round trips + session decode +
# settings GROUP BY this endpoint runs cold. Library / Group writes
# call ``cache.clear()`` in their viewsets, which evicts these keys
# alongside cachalot's ORM cache.
_CACHE_TTL_SECONDS: Final = 60
_CACHE_KEY_PREFIX: Final = "admin-stats:"


class AdminStatsView(AdminGenericAPIView):
    """Admin Flag Viewset."""

    permission_classes = (HasAPIKeyOrIsAdminUser,)
    serializer_class = StatsSerializer
    input_serializer_class = AdminStatsRequestSerializer

    def __init__(self, *args, **kwargs) -> None:
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

    def _add_api_key(self, obj) -> None:
        """Add the api key to the config object if specified."""
        request_counts = self.params.get("config", {})
        if request_counts and ("apikey" not in request_counts):
            return
        api_key = Timestamp.objects.get(key=Timestamp.Choices.API_KEY.value).version
        if "config" not in obj:
            obj["config"] = {}
        obj["config"]["api_key"] = api_key

    def _cache_key(self) -> str:
        """Deterministic cache key derived from the requested params."""
        # ``MappingProxyType`` isn't directly JSON-serializable, but the
        # values are. Re-render through a regular dict so ``sort_keys``
        # gives a stable digest across requests with the same shape.
        param_str = json.dumps(dict(self.params), sort_keys=True, default=str)
        digest = hashlib.sha256(param_str.encode("utf-8")).hexdigest()[:16]
        return f"{_CACHE_KEY_PREFIX}{digest}"

    @override
    def get_object(self) -> dict:
        """Get (or build) the cached stats object plus a fresh api key."""
        cache_key = self._cache_key()
        # Cache the heavy stats payload only; the api key is sourced
        # outside the cache so a key rotation is reflected immediately.
        cached = cache.get(cache_key)
        if cached is None:
            getter = CodexStats(self.params)
            cached = getter.get()
            cache.set(cache_key, cached, _CACHE_TTL_SECONDS)
        obj = deepcopy(cached)
        self._add_api_key(obj)
        return obj

    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs) -> Response:
        """Get the stats object and serialize it."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

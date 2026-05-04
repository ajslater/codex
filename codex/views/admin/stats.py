"""Admin Stats View."""

import hashlib
import json
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Final

from adrf.mixins import get_data
from asgiref.sync import sync_to_async
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.librarian.telemeter.stats import CodexStats
from codex.models.admin import Timestamp
from codex.serializers.admin.stats import (
    AdminStatsRequestSerializer,
    StatsSerializer,
)
from codex.views.admin.auth import AsyncAdminGenericAPIView
from codex.views.admin.permissions import HasAPIKeyOrIsAdminUser

# Cache TTL for the assembled stats object. The data underneath only
# changes as the librarian imports / users sign up — a brief staleness
# window beats the ~30 ``COUNT(*)`` round trips + session decode +
# settings GROUP BY this endpoint runs cold. Library / Group writes
# call ``cache.clear()`` in their viewsets, which evicts these keys
# alongside cachalot's ORM cache.
_CACHE_TTL_SECONDS: Final = 60
_CACHE_KEY_PREFIX: Final = "admin-stats:"


class AdminStatsView(AsyncAdminGenericAPIView):
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
            # ``validated_data`` is always a populated dict at this
            # point (``is_valid(raise_exception=True)`` guarantees it),
            # so a per-item guard checking the parent for emptiness was
            # dead code. Wrap directly.
            self._params = MappingProxyType(dict(input_serializer.validated_data))
        return self._params

    async def _aadd_api_key(self, obj) -> None:
        """Add the api key to the config object if specified."""
        request_counts = self.params.get("config", {})
        if request_counts and ("apikey" not in request_counts):
            return
        api_key = (
            await Timestamp.objects.aget(key=Timestamp.Choices.API_KEY.value)
        ).version
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

    async def _aget_stats(self) -> dict:
        """Get (or build) the cached stats object plus a fresh api key."""
        cache_key = self._cache_key()
        # Cache the heavy stats payload only; the api key is sourced
        # outside the cache so a key rotation is reflected immediately.
        cached = await cache.aget(cache_key)
        if cached is None:
            # ``CodexStats.get`` runs ~30 sync COUNT/GROUP BY queries.
            # Off-load it from the event loop; ``thread_sensitive=False``
            # lets concurrent stats requests run on separate workers.
            cached = await sync_to_async(
                CodexStats(self.params).get, thread_sensitive=False
            )()
            await cache.aset(cache_key, cached, _CACHE_TTL_SECONDS)
        obj = deepcopy(cached)
        await self._aadd_api_key(obj)
        return obj

    @extend_schema(parameters=[input_serializer_class])
    async def get(self, *_args, **_kwargs) -> Response:
        """Get the stats object and serialize it."""
        obj = await self._aget_stats()
        serializer = self.get_serializer(obj)
        return Response(await get_data(serializer))

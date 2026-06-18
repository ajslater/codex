"""Parse browser params."""

from collections.abc import Mapping, MutableMapping
from types import MappingProxyType
from typing import Any

from loguru import logger

from codex.librarian.bookmark.tasks import LastRouteUpdateTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.serializers.browser.settings import (
    BrowserSettingsSerializer,
    BrowserSettingsSerializerBase,
)
from codex.views.browser.settings import BrowserSettingsBaseView


class BrowserParamsView(BrowserSettingsBaseView):
    """Browser Params Parsing."""

    input_serializer_class: type[BrowserSettingsSerializerBase] = (
        BrowserSettingsSerializer
    )

    def __init__(self, *args, **kwargs) -> None:
        """Initialize properties."""
        super().__init__(*args, **kwargs)
        self._params: MappingProxyType[str, Any] | None = None

    def init_params(self) -> MutableMapping[str, Any]:
        """Get params from stored settings and request."""
        serializer = self.input_serializer_class(data=self.request.GET)
        serializer.is_valid(raise_exception=True)
        params = self.load_params_from_settings()
        if serializer.validated_data:
            params.update(serializer.validated_data)
        return params

    def _update_last_route(self, data: MutableMapping) -> bool:
        """Save last route to data; return True when the route changed."""
        last_route = data.get("last_route", {})
        new_route = {
            "collection": self.kwargs.get("collection", "root"),
            "pks": self.kwargs.get("pks", (0,)),
            "page": self.kwargs.get("page", 1),
        }
        changed = (
            last_route.get("collection") != new_route["collection"]
            or tuple(last_route.get("pks") or (0,)) != tuple(new_route["pks"] or (0,))
            or last_route.get("page") != new_route["page"]
        )
        last_route.update(new_route)
        data["last_route"] = last_route
        return changed

    def _queue_last_route_update(self, route: Mapping) -> None:
        """
        Persist the route via the librarian writer, off the request thread.

        The synchronous save made every navigation a write transaction
        on the read path: it stalled behind the WAL writer lock during
        imports (measured 1.85s vs 12ms) and evicted cachalot's settings
        cache for everyone. The bookmark thread debounces these per
        settings row.
        """
        instance = self._settings_instances.get((self.MODEL, self.CLIENT))
        if instance is None:
            return
        task = LastRouteUpdateTask(settings_pk=instance.pk, route=dict(route))
        LIBRARIAN_QUEUE.put(task)

    def set_params(self, params: Mapping) -> None:
        """Manually set the params."""
        self._params = MappingProxyType(params)

    @property
    def params(self) -> MappingProxyType:
        """Validate submitted settings and apply them over the session settings."""
        if self._params is None:
            try:
                params = self.init_params()
                route_changed = self._update_last_route(params)
                self.save_params_to_settings(params, defer_last_route=True)
                if route_changed:
                    self._queue_last_route_update(params["last_route"])
                self.set_order_by_default(params)
                self.set_params(params)
            except Exception as exc:
                # for debugging if this goes awry
                logger.exception(exc)
                raise
        return self._params  # pyright: ignore[reportReturnType], # ty: ignore[invalid-return-type]

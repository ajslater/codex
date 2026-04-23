"""Parse browser params."""

from collections.abc import Mapping, MutableMapping
from types import MappingProxyType
from typing import Any

from loguru import logger

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

    def _update_last_route(self, data: MutableMapping) -> None:
        """Save last route to data."""
        last_route = data.get("last_route", {})
        last_route.update(
            {
                "group": self.kwargs.get("group", "r"),
                "pks": self.kwargs.get("pks", (0,)),
                "page": self.kwargs.get("page", 1),
            }
        )
        data["last_route"] = last_route

    def set_params(self, params: Mapping) -> None:
        """Manually set the params."""
        self._params = MappingProxyType(params)

    @property
    def params(self) -> MappingProxyType:
        """Validate submitted settings and apply them over the session settings."""
        if self._params is None:
            try:
                params = self.init_params()
                self._update_last_route(params)
                self.save_params_to_settings(params)
                self.set_order_by_default(params)
                self.set_params(params)
            except Exception as exc:
                # for debugging if this goes awry
                logger.exception(exc)
                raise
        return self._params  # pyright: ignore[reportReturnType], # ty: ignore[invalid-return-type]

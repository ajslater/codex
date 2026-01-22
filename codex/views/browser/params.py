"""Parse browser params."""

from types import MappingProxyType
from typing import Any

from codex.serializers.browser.settings import (
    BrowserSettingsSerializer,
    BrowserSettingsSerializerBase,
)
from codex.views.session import SessionView


class BrowserParamsView(SessionView):
    """Browser Params Parsing."""

    input_serializer_class: type[BrowserSettingsSerializerBase] = (
        BrowserSettingsSerializer
    )

    def __init__(self, *args, **kwargs):
        """Initialize properties."""
        super().__init__(*args, **kwargs)
        self._params: MappingProxyType[str, Any] | None = None

    @property
    def params(self):
        """Validate submitted settings and apply them over the session settings."""
        if self._params is None:
            serializer = self.input_serializer_class(data=self.request.GET)
            serializer.is_valid(raise_exception=True)
            params = self.load_params_from_session()
            if serializer.validated_data:
                params.update(serializer.validated_data)
            self.save_last_route(params)
            self.save_params_to_session(params)
            self._params = MappingProxyType(params)
        return self._params

    def set_params(self, params):
        """Manually set the params."""
        self._params = params

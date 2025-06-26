"""Parse browser params."""

from types import MappingProxyType
from typing import Any

from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.views.const import FOLDER_GROUP, STORY_ARC_GROUP
from codex.views.session import SessionView


class BrowserParamsView(SessionView):
    """Browser Params Parsing."""

    input_serializer_class: type[BrowserSettingsSerializer] = BrowserSettingsSerializer

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

            params: dict[str, Any] = {}
            defaults = self.SESSION_DEFAULTS[self.SESSION_KEY]
            params.update(defaults)
            group = self.kwargs.get("group")
            if group:
                # order_by has a dynamic group based default
                order_defaults = {
                    "order_by": "filename"
                    if group == FOLDER_GROUP
                    else "story_arc_number"
                    if group == STORY_ARC_GROUP
                    else "sort_name"
                }
                params.update(order_defaults)
            validated_data = serializer.validated_data

            if validated_data:
                params.update(validated_data)
            self._params = MappingProxyType(params)
        return self._params

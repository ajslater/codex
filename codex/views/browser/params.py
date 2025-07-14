"""Parse browser params."""

from types import MappingProxyType
from typing import Any

from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.util import mapping_to_dict
from codex.views.const import FOLDER_GROUP, STORY_ARC_GROUP
from codex.views.session import SessionView


class BrowserParamsView(SessionView):
    """Browser Params Parsing."""

    input_serializer_class: type[BrowserSettingsSerializer] = BrowserSettingsSerializer

    def __init__(self, *args, **kwargs):
        """Initialize properties."""
        super().__init__(*args, **kwargs)
        self._params: MappingProxyType[str, Any] | None = None

    def _get_order_defaults(self) -> dict:
        if group := self.kwargs.get("group"):
            # order_by has a dynamic group based default
            order_by = (
                "filename"
                if group == FOLDER_GROUP
                else "story_arc_number"
                if group == STORY_ARC_GROUP
                else "sort_name"
            )
            order_defaults = {"order_by": order_by}
        else:
            order_defaults = {}
        return order_defaults

    @property
    def params(self):
        """Validate submitted settings and apply them over the session settings."""
        if self._params is None:
            serializer = self.input_serializer_class(data=self.request.GET)
            serializer.is_valid(raise_exception=True)

            params = mapping_to_dict(self.SESSION_DEFAULTS[self.SESSION_KEY])
            if serializer.validated_data:
                params.update(serializer.validated_data)
            if order_defaults := self._get_order_defaults():
                params.update(order_defaults)
            self.save_params_to_session(params)
            self._params = MappingProxyType(params)
        return self._params

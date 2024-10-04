"""Parse browser params."""

from types import MappingProxyType
from typing import Any

from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.views.const import FOLDER_GROUP, STORY_ARC_GROUP
from codex.views.session import SessionView
from codex.views.util import reparse_json_query_params


class BrowserParamsView(SessionView):
    """Browser Params Parsing."""

    input_serializer_class = BrowserSettingsSerializer
    REPARSE_JSON_FIELDS = frozenset({"breadcrumbs", "filters", "show"})

    def __init__(self, *args, **kwargs):
        """Initialize properties."""
        super().__init__(*args, **kwargs)
        self._params: MappingProxyType[str, Any] | None = None

    def _parse_query_params(self):
        """Parse GET query parameters: filter object & snake case."""
        query_params = reparse_json_query_params(
            self.request.GET, self.REPARSE_JSON_FIELDS
        )
        if "q" not in query_params and (query := query_params.get("query")):
            # parse query param for opds v2
            query_params["q"] = query
        return query_params

    def validate_settings(self):
        """Not used until browser/validate.py."""

    @property
    def params(self):
        """Validate sbmitted settings and apply them over the session settings."""
        if self._params is None:
            data = self._parse_query_params()
            serializer = self.input_serializer_class(data=data)
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
                params.update(validated_data)  # type: ignore
            self._params = MappingProxyType(params)
            self.validate_settings()
        return self._params

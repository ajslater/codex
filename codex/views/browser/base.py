"""Views for browsing comic library."""

from types import MappingProxyType
from typing import Any

from rest_framework.exceptions import NotFound

from codex.logger.logging import get_logger
from codex.models.groups import BrowserGroupModel
from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.views.browser.filters.search.parse import SearchFilterView
from codex.views.const import FOLDER_GROUP, GROUP_MODEL_MAP, ROOT_GROUP, STORY_ARC_GROUP
from codex.views.util import reparse_json_query_params

LOG = get_logger(__name__)


class BrowserBaseView(SearchFilterView):
    """Browse comics with a variety of filters and sorts."""

    input_serializer_class = BrowserSettingsSerializer

    REPARSE_JSON_FIELDS = frozenset({"breadcrumbs", "filters", "show"})

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self._is_admin: bool | None = None
        self.params: MappingProxyType[str, Any] = MappingProxyType({})
        self._model_group: str = ""
        self._model: type[BrowserGroupModel] | None = None
        self._rel_prefix: str | None = None

    @property
    def model_group(self):
        """Memoize the model group."""
        if not self._model_group:
            group = self.kwargs["group"]
            if group == ROOT_GROUP:
                group = self.params["top_group"]
            self._model_group = group
        return self._model_group

    @property
    def model(self) -> type[BrowserGroupModel] | None:
        """Memoize the model for the browse list."""
        if not self._model:
            model = GROUP_MODEL_MAP.get(self.model_group)
            if model is None:
                group = self.kwargs["group"]
                detail = f"Cannot browse {group=}"
                LOG.debug(detail)
                raise NotFound(detail=detail)
            self._model = model
        return self._model

    @property
    def rel_prefix(self):
        """Memoize model rel prefix."""
        if self._rel_prefix is None:
            self._rel_prefix = self.get_rel_prefix(self.model)
        return self._rel_prefix

    def _parse_query_params(self):
        """Parse GET query parameters: filter object & snake case."""
        query_params = reparse_json_query_params(
            self.request.GET, self.REPARSE_JSON_FIELDS
        )
        if "q" not in query_params and (query := query_params.get("query")):
            # parse query param for opds v2
            query_params["q"] = query
        return query_params

    def parse_params(self):
        """Validate sbmitted settings and apply them over the session settings."""
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
        self.params = MappingProxyType(params)
        self.is_bookmark_filtered = bool(self.params.get("filters", {}).get("bookmark"))

    def validate_settings(self):
        """Unused until browser."""

    def init_request(self):
        """Initialize request."""
        self.parse_params()
        self.validate_settings()

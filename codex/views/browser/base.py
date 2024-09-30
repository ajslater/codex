"""Views for browsing comic library."""

from rest_framework.exceptions import NotFound

from codex.logger.logging import get_logger
from codex.models.groups import BrowserGroupModel
from codex.views.browser.filters.search.parse import SearchFilterView
from codex.views.const import GROUP_MODEL_MAP, ROOT_GROUP

LOG = get_logger(__name__)


class BrowserBaseView(SearchFilterView):
    """Browse comics with a variety of filters and sorts."""

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self._is_admin: bool | None = None
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

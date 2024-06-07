"""Get the mtimes for the submitted groups."""

from types import MappingProxyType

from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.models.groups import Publisher
from codex.serializers.browser.mtime import GroupsMtimeSerializer, MtimeSerializer
from codex.util import max_none
from codex.views.browser.filters.annotations import BrowserAnnotationsFilterView
from codex.views.const import GROUP_MODEL_MAP

LOG = get_logger(__name__)


class MtimeView(BrowserAnnotationsFilterView):
    """Get the mtimes for the submitted groups."""

    input_serializer_class = GroupsMtimeSerializer
    serializer_class = MtimeSerializer

    REPARSE_JSON_FIELDS = frozenset({"groups", "filters"})

    def __init__(self, *args, **kwargs) -> None:
        """Initialize."""
        super().__init__(*args, **kwargs)
        self.init_bookmark_data()

    def parse_params(self):
        """Parse GET params."""
        try:
            validated_data = super().parse_params()
            params = dict(self.params)
            params["groups"] = validated_data["groups"]  # type: ignore
            self.params = MappingProxyType(params)

        except Exception:
            LOG.exception("parse")
            raise

    def _get_group_mtime(self, item):
        """Get one group's mtimes."""
        group = item["group"]
        pks = item["pks"]

        model = GROUP_MODEL_MAP[group]
        if not model:
            model = Publisher

        return self.get_group_mtime(model, group, pks)

    def get_max_groups_mtime(self):
        """Get max mtime for all groups."""
        max_mtime = None

        for item in self.params["groups"]:  # type: ignore
            mtime = self._get_group_mtime(item)
            max_mtime = max_none(max_mtime, mtime)
        return max_mtime

    def get(self, *args, **kwargs):
        """Get the mtimes for the submitted groups."""
        # Parse Request
        self.parse_params()

        max_mtime = self.get_max_groups_mtime()

        # Serialize Response
        result = {"max_mtime": max_mtime}
        serializer = self.get_serializer(result)
        return Response(serializer.data)

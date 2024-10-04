"""Get the mtimes for the submitted groups."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.models.groups import Publisher
from codex.serializers.browser.mtime import GroupsMtimeSerializer, MtimeSerializer
from codex.util import max_none
from codex.views.browser.group_mtime import BrowserGroupMtimeView
from codex.views.const import GROUP_MODEL_MAP

LOG = get_logger(__name__)


class MtimeView(BrowserGroupMtimeView):
    """Get the mtimes for the submitted groups."""

    input_serializer_class = GroupsMtimeSerializer
    serializer_class = MtimeSerializer

    REPARSE_JSON_FIELDS = frozenset({"groups", "filters"})
    TARGET = "mtime"

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

    @extend_schema(parameters=[GroupsMtimeSerializer])
    def get(self, *args, **kwargs):
        """Get the mtimes for the submitted groups."""
        max_mtime = self.get_max_groups_mtime()

        # Serialize Response
        result = {"max_mtime": max_mtime}
        serializer = self.get_serializer(result)
        return Response(serializer.data)

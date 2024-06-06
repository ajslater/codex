"""Get the mtimes for the submitted groups."""

from django.db.models import Max
from rest_framework.response import Response

from codex.models.groups import Publisher
from codex.serializers.mtime import GroupsMtimeSerializer, MtimeSerializer
from codex.util import max_none
from codex.views.auth import AuthGenericAPIView
from codex.views.browser.filters.bookmark import BookmarkFilterMixin
from codex.views.const import GROUP_MODEL_MAP
from codex.views.util import reparse_json_query_params

_REPARSE_JSON_FIELDS = frozenset({"groups"})


class MtimeView(AuthGenericAPIView, BookmarkFilterMixin):
    """Get the mtimes for the submitted groups."""

    serializer_class = GroupsMtimeSerializer
    response_serializer_class = MtimeSerializer

    def _parse_params(self):
        params = reparse_json_query_params(self.request.GET, _REPARSE_JSON_FIELDS)
        self.groups = params.get("groups", "")
        self.use_bookmark_filter = self.request.GET.get("use_bookmark_filter", False)

    def _get_group_mtime(self, group, pks):
        """Get one group's mtimes."""
        model = GROUP_MODEL_MAP[group]
        if not model:
            model = Publisher

        qs = model.objects.all()

        if pks and 0 not in pks:
            qs = qs.filter(pk__in=pks)
        updated_at_max = qs.aggregate(max=Max("updated_at"))["max"]

        if self.use_bookmark_filter:
            bm_rel = self.get_bm_rel(model)
            bm_filter = self.get_my_bookmark_filter(bm_rel)
            qs = qs.filter(bm_filter)
            bookmark_updated_at_max = qs.aggregate(max=(Max(f"{bm_rel}__updated_at")))[
                "max"
            ]
            updated_at_max = max_none(updated_at_max, bookmark_updated_at_max)

        return updated_at_max

    def get_max_groups_mtime(self):
        """Get max mtime for all groups."""
        max_mtime = None

        for item in self.groups:
            group = item["group"]
            pks = tuple(int(pk) for pk in item["pks"].split(","))
            mtime = self._get_group_mtime(group, pks)
            max_mtime = max_none(max_mtime, mtime)
        return max_mtime

    def get(self, *args, **kwargs):
        """Get the mtimes for the submitted groups."""
        # Parse Request
        self._parse_params()

        max_mtime = self.get_max_groups_mtime()

        # Serialize Response
        result = {"max_mtime": max_mtime}
        serializer = self.response_serializer_class(result)
        return Response(serializer.data)

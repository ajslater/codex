"""Get the mtimes for the submitted groups."""

from django.db.models import Max
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from codex.models.groups import Publisher
from codex.serializers.mtime import GroupsMtimeSerializer, MtimeSerializer
from codex.util import max_none
from codex.views.browser.filters.bookmark import BookmarkFilterMixin
from codex.views.const import GROUP_MODEL_MAP
from codex.views.utils import reparse_json_query_params

REPARSE_JSON_FIELDS = frozenset({"groups"})

class MtimeView(GenericAPIView, BookmarkFilterMixin):
    """Get the mtimes for the submitted groups."""

    serializer_class = GroupsMtimeSerializer
    response_serializer_class = MtimeSerializer

    def _get_group_mtime(self, group, pks, use_bookmark_filter):
        """Get one group's mtimes."""
        model = GROUP_MODEL_MAP[group]
        if not model:
            model = Publisher

        qs = model.objects

        if pks and 0 not in pks:
            qs = qs.filter(pk__in=pks)
        updated_at_max = qs.aggregate(max=Max("updated_at"))["max"]

        if use_bookmark_filter:
            bm_rel = self.get_bm_rel(model)
            bm_filter = self.get_my_bookmark_filter(bm_rel)
            qs = qs.filter(bm_filter)
            # TODO can these be combined into one max?
            bookmark_updated_at_max = qs.aggregate(max=(Max(f"{bm_rel}__updated_at")))[
                "max"
            ]
            updated_at_max = max_none(updated_at_max, bookmark_updated_at_max)

        return updated_at_max

    def get_max_groups_mtime(self, groups, use_bookmark_filter):
        """Get max mtime for all groups."""
        max_mtime = None

        for item in groups:
            group = item["group"]
            pks = tuple(int(pk) for pk in item["pks"].split(","))
            mtime = self._get_group_mtime(group, pks, use_bookmark_filter)
            max_mtime = max_none(max_mtime, mtime)
        return max_mtime

    def get(self, *args, **kwargs):
        """Get the mtimes for the submitted groups."""
        # Parse Request
        params = reparse_json_query_params(self.request.GET, REPARSE_JSON_FIELDS)
        groups = params.get("groups", "")
        use_bookmark_filter = self.request.GET.get("use_bookmark_filter", False)

        max_mtime = self.get_max_groups_mtime(groups, use_bookmark_filter)

        # Serialize Response
        result = {"max_mtime": max_mtime}
        serializer = self.response_serializer_class(result)
        return Response(serializer.data)

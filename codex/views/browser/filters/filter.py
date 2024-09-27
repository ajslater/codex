"""Browser Filters."""

from django.db.models.aggregates import Count
from django.db.models.query_utils import Q

from codex.logger.logging import get_logger
from codex.models.comic import Comic
from codex.views.browser.filters.bookmark import BrowserFilterBookmarkView
from codex.views.const import ONE_INTEGERFIELD

_CHILD_COUNT = "child_count"
LOG = get_logger(__name__)


class BrowserFilterView(BrowserFilterBookmarkView):
    """Browser Filters."""

    TARGET = ""

    def _filter_by_child_count(self, qs):
        """Filter group by child count."""
        rel = self.rel_prefix + "pk"
        count_func = (
            ONE_INTEGERFIELD if qs.model is Comic else Count(rel, distinct=True)
        )
        ann = {_CHILD_COUNT: count_func}
        if self.TARGET == "opds2":
            if qs.model is not Comic:
                qs = qs.alias(**ann)
        else:
            # This is the only annotation to happen during the filter for efficiency
            qs = qs.annotate(**ann)
        if qs.model is not Comic:
            # qs = qs.filter(**{f"{_CHILD_COUNT}__gt": 0})
            # TODO if this works move childcount annotation to annotations
            qs = qs.filter(comic__isnull=False)
        return qs

    def _get_query_filters(  # noqa: PLR0913
        self,
        model,
        group,
        pks,
        bookmark_filter,
        page_mtime=False,
        group_filter=True,
        acl_filter=True,
    ):
        """Return all the filters except the group filter."""
        # XXX all these ifs and flags are awful
        object_filter = Q()
        if acl_filter:
            object_filter &= self.get_group_acl_filter(model)
        if group_filter:
            object_filter &= self.get_group_filter(group, pks, page_mtime=page_mtime)
        object_filter &= self.get_comic_field_filter(model)
        if bookmark_filter:
            # not needed when used by outerrefl OuterRef is applied next
            object_filter &= self.get_bookmark_filter(model)
        return object_filter

    def get_filtered_queryset(  # noqa: PLR0913
        self,
        model,
        group=None,
        pks=None,
        bookmark_filter=True,
        page_mtime=False,
        group_filter=True,
        acl_filter=True,
    ):
        """Get a filtered queryset for the model."""
        object_filter = self._get_query_filters(
            model,
            group,
            pks,
            bookmark_filter,
            page_mtime=page_mtime,
            group_filter=group_filter,
            acl_filter=acl_filter,
        )
        qs = model.objects.filter(object_filter)
        qs = self.apply_search_filter(qs)
        return self._filter_by_child_count(qs)

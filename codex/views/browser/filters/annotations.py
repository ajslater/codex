"""Annotations used by a filter."""

from django.db.models.aggregates import Count, Max
from django.db.models.functions import Coalesce, Greatest

from codex.models.comic import Comic
from codex.views.browser.filters.bookmark import BookmarkFilterMixin
from codex.views.browser.validate import BrowserValidateView
from codex.views.const import (
    EPOCH_START_DATETIMEFIELD,
    ONE_INTEGERFIELD,
)

_CHILD_COUNT = "child_count"


class BrowserAnnotationsFilterView(BrowserValidateView, BookmarkFilterMixin):
    """Annotations that also filter."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize."""
        super().__init__(*args, **kwargs)
        self.init_bookmark_data()

    def _get_query_filters(  # noqa: PLR0913
        self, model, group, pks, bookmark_filter, page_mtime=False, group_filter=True
    ):
        """Return all the filters except the group filter."""
        # XXX all these ifs and flags are awful
        object_filter = self.get_group_acl_filter(model)
        if group_filter:
            object_filter &= self.get_group_filter(group, pks, page_mtime=page_mtime)
        object_filter &= self.get_comic_field_filter(model)
        if bookmark_filter:
            # not needed when used by outerrefl OuterRef is applied next
            object_filter &= self.get_bookmark_filter(model)
        return object_filter

    def _filter_by_child_count(self, qs, model):
        """Filter group by child count."""
        rel = self.rel_prefix + "pk"
        count_func = ONE_INTEGERFIELD if model == Comic else Count(rel, distinct=True)
        ann = {_CHILD_COUNT: count_func}
        if self.TARGET == "opds2":
            if model != Comic:
                qs = qs.alias(**ann)
        else:
            qs = qs.annotate(**ann)
        if model != Comic:
            qs = qs.filter(**{f"{_CHILD_COUNT}__gt": 0})
        return qs

    def get_filtered_queryset(  # noqa: PLR0913
        self,
        model,
        group=None,
        pks=None,
        bookmark_filter=True,
        page_mtime=False,
        group_filter=True,
    ):
        """Get a filtered queryset for the model."""
        object_filter = self._get_query_filters(
            model,
            group,
            pks,
            bookmark_filter,
            page_mtime=page_mtime,
            group_filter=group_filter,
        )
        qs = model.objects.filter(object_filter)
        qs = self.apply_search_filter(qs, model)
        return self._filter_by_child_count(qs, model)

    def get_group_mtime(self, model, group=None, pks=None, page_mtime=False):
        """Get a filtered mtime for browser pages and mtime checker."""
        qs = self.get_filtered_queryset(
            model,
            group=group,
            pks=pks,
            bookmark_filter=self.is_bookmark_filtered,
            page_mtime=page_mtime,
        )
        qs = qs.annotate(max_updated_at=Max("updated_at"))

        if self.is_bookmark_filtered:
            bm_rel, bm_filter = self.get_bookmark_rel_and_filter(model)
            qs = qs.filter(bm_filter)
            ua_rel = bm_rel + "__updated_at"
            mbua = Max(ua_rel)
        else:
            mbua = EPOCH_START_DATETIMEFIELD
        qs = qs.annotate(max_bookmark_updated_at=mbua)

        mtime = qs.aggregate(
            max=Greatest(
                Coalesce("max_bookmark_updated_at", EPOCH_START_DATETIMEFIELD),
                "max_updated_at",
            )
        )["max"]
        if mtime == NotImplemented:
            mtime = None
        return mtime

"""Annotations used by a filter."""

from django.db.models.aggregates import Count

from codex.models.comic import Comic
from codex.views.browser.filters.bookmark import BookmarkFilterMixin
from codex.views.browser.validate import BrowserValidateView


class BrowserAnnotationsFilterView(BrowserValidateView, BookmarkFilterMixin):
    """Annotations that also filter."""

    def get_query_filters(self, model):
        """Return all the filters except the group filter."""
        object_filter = self.get_group_acl_filter(model)
        object_filter &= self.get_bookmark_filter(model)
        object_filter &= self.get_comic_field_filter(model)
        object_filter &= self.get_group_filter(model)
        return object_filter

    def _filter_by_child_count(self, qs, model):
        if model == Comic:
            return qs

        rel = self.rel_prefix + "pk"
        qs = qs.alias(pre_search_child_count=Count(rel, distinct=True))
        return qs.filter(pre_search_child_count__gt=0)

    def get_filtered_queryset(self, model):
        """Get a filtered queryset for the model."""
        object_filter = self.get_query_filters(model)

        qs = model.objects.filter(object_filter)
        qs = self._filter_by_child_count(qs, model)
        return self.apply_search_filter(qs, model)

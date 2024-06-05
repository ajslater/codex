"""Annotations used by a filter."""

from django.db.models.aggregates import Count

from codex.models.comic import Comic
from codex.views.browser.validate import BrowserValidateView


class BrowserAnnotationsFilterView(BrowserValidateView):
    """Annotations that also filter."""

    def _filter_by_child_count(self, qs, model):
        if model == Comic:
            return qs

        rel = self.rel_prefix + "pk"
        qs = qs.alias(pre_search_child_count=Count(rel, distinct=True))
        return qs.filter(pre_search_child_count__gt=0)

    def filter_by_annotations(self, qs, model, binary=False):
        """Filter queryset by annotations."""
        qs = self._filter_by_child_count(qs, model)
        return self.apply_search_filter(qs, model, binary=binary)

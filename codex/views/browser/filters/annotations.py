"""Annotations used by a filter."""

from django.db.models.aggregates import Count
from django.db.models.expressions import Value
from django.db.models.fields import PositiveSmallIntegerField

from codex.models.comic import Comic
from codex.views.browser.base import BrowserBaseView


class BrowserAnnotationsFilterView(BrowserBaseView):
    """Annotations that also filter."""

    ONE_INTEGERFIELD = Value(1, PositiveSmallIntegerField())

    def _annotate_child_count(self, qs, model):
        """Annotate Child Count."""
        if model == Comic:
            child_count_sum = self.ONE_INTEGERFIELD
        else:
            child_count_sum = Count(self.rel_prefix + "pk", distinct=True)
        if self.TARGET == "opds2":
            if model != Comic:
                qs = qs.alias(child_count=child_count_sum)
        else:
            qs = qs.annotate(child_count=child_count_sum)
        if model != Comic:
            qs = qs.filter(child_count__gt=0)
        return qs

    def filter_by_annotations(self, qs, model, binary=False):
        """Filter queryset by annotations."""
        qs = self._annotate_child_count(qs, model)
        return self.apply_search_filter(qs, model, binary=binary)

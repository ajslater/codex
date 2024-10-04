"""Base view for metadata annotations."""

from types import MappingProxyType

from django.db.models import (
    Value,
)
from django.db.models.aggregates import Count
from django.db.models.fields import CharField

from codex.logger.logging import get_logger
from codex.models.comic import Comic
from codex.models.functions import JsonGroupArray
from codex.models.groups import BrowserGroupModel, Imprint, Publisher, Series, Volume
from codex.views.browser.annotate.bookmark import BrowserAnnotateBookmarkView

_GROUP_BY: MappingProxyType[type[BrowserGroupModel], str] = MappingProxyType(
    {Publisher: "sort_name", Imprint: "sort_name", Series: "sort_name", Volume: "name"}
)
LOG = get_logger(__name__)


class BrowserAnnotateCardView(BrowserAnnotateBookmarkView):
    """Base class for views that need special metadata annotations."""

    def add_group_by(self, qs):
        """Get the group by for the model."""
        if group_by := _GROUP_BY.get(qs.model):  # type: ignore
            qs = qs.group_by(group_by)
        return qs

    def _annotate_child_count(self, qs):
        """Annotate child chount for card."""
        if qs.model is Comic:
            return qs
        rel = self.rel_prefix + "pk"
        count_func = Count(rel, distinct=True)
        ann = {"child_count": count_func}
        if self.TARGET == "opds2":
            if qs.model is not Comic:
                qs = qs.alias(**ann)
        else:
            qs = qs.annotate(**ann)
        return qs

    def _annotate_group(self, qs):
        """Annotate Group."""
        value = "c" if qs.model is Comic else self.model_group  # type: ignore
        return qs.annotate(group=Value(value, CharField(max_length=1)))

    def annotate_card_aggregates(self, qs):
        """Annotate aggregates that appear the browser card."""
        if qs.model is Comic:
            # comic adds order_value for cards late
            qs = self.annotate_order_value(qs)
        qs = self._annotate_group(qs)
        qs = self.annotate_group_names(qs)
        qs = self._annotate_child_count(qs)
        qs = self.annotate_bookmarks(qs)
        qs = self.annotate_progress(qs)
        return qs.annotate(updated_ats=JsonGroupArray("updated_at", distinct=True))

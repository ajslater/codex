"""Base view for metadata annotations."""

from types import MappingProxyType

from django.db.models import (
    F,
    Value,
)
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
        if group_by := _GROUP_BY.get(qs.model):
            qs = qs.group_by(group_by)
        return qs

    def _annotate_group(self, qs):
        """Annotate Group."""
        value = "c" if qs.model is Comic else self.model_group
        return qs.annotate(group=Value(value, CharField(max_length=1)))

    def _annotate_file_name(self, qs):
        """Annotate the file name for folder view."""
        if qs.model is not Comic:
            return qs
        if self.order_key == "filename":
            file_name = F("filename")
        else:
            file_name = self.get_filename_func(qs.model)
        return qs.annotate(file_name=file_name)

    def annotate_card_aggregates(self, qs):
        """Annotate aggregates that appear the browser card."""
        if qs.model is Comic:
            # comic adds order_value for cards late
            qs = self.annotate_order_value(qs)
        qs = self._annotate_group(qs)
        qs = self.annotate_group_names(qs)
        qs = self._annotate_file_name(qs)
        qs = self.annotate_child_count(qs)
        qs = self.annotate_bookmarks(qs)
        qs = self.annotate_progress(qs)
        return qs.annotate(updated_ats=JsonGroupArray("updated_at", distinct=True))

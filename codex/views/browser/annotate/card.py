"""Base view for metadata annotations."""

from django.db.models import (
    Value,
)
from django.db.models.fields import CharField

from codex.logger.logging import get_logger
from codex.models import (
    BrowserGroupModel,
    Comic,
)
from codex.models.functions import JsonGroupArray
from codex.views.browser.annotate.bookmark import BrowserAnnotateBookmarkView

LOG = get_logger(__name__)


class BrowserAnnotateCardView(BrowserAnnotateBookmarkView):
    """Base class for views that need special metadata annotations."""

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self.is_opds_1_acquisition = False
        self.comic_sort_names = ()
        self.bm_annotataion_data: dict[BrowserGroupModel, tuple[str, dict]] = {}

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
        qs = self.annotate_bookmarks(qs)
        qs = self.annotate_progress(qs)
        return qs.annotate(updated_ats=JsonGroupArray("updated_at", distinct=True))

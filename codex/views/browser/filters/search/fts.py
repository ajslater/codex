"""Search Filters Methods."""

from django.db.models.query import Q

from codex.logger.logging import get_logger
from codex.models import Comic, StoryArc
from codex.views.browser.filters.search.field.filter import BrowserFieldQueryFilter

LOG = get_logger(__name__)


class BrowserFTSFilter(BrowserFieldQueryFilter):
    """Search Filters Methods."""

    @staticmethod
    def _get_fts_filter(model, text):
        """Get the filter dict."""
        prefix = (
            ""
            if model == Comic
            else "storyarcnumber__comic__"
            if model == StoryArc
            else "comic__"
        )
        # Custom Lookup defined in codex.models
        rel = prefix + "comicfts__match"
        return {rel: text}

    def get_fts_filter(self, model, text):
        """Perform the search and return the scores as a dict."""
        fts_filter = {}
        try:
            if text:
                fts_filter = self._get_fts_filter(model, text)
        except Exception:
            LOG.exception("Getting Full Text Search Filter.")
            self.search_error = "Error creating full text search filter"
        return Q(**fts_filter)

"""Search Filters Methods."""

from codex.logger.logging import get_logger
from codex.views.browser.filters.search.field.filter import BrowserFieldQueryFilter

LOG = get_logger(__name__)


class BrowserFTSFilter(BrowserFieldQueryFilter):
    """Search Filters Methods."""

    def get_fts_filter(self, model, text):
        """Perform the search and return the scores as a dict."""
        fts_filter = {}
        try:
            if text:
                rel = self.get_rel_prefix(model)
                # Custom lookup defined in codex.models
                rel += "comicfts__match"
                fts_filter[rel] = text
        except Exception:
            LOG.exception("Getting Full Text Search Filter.")
            self.search_error = "Error creating full text search filter"
        return fts_filter

"""Search Filters Methods."""

from codex.logger.logging import get_logger
from codex.views.browser.filters.search.fts import BrowserFTSFilter

LOG = get_logger(__name__)


class SearchFilterView(BrowserFTSFilter):
    """Search Query Parser."""

    def apply_search_filter(self, qs, model):
        """Preparse search, search and return the filter and scores."""
        try:
            field_tokens, text = self.preparse_search_query()
            qs = self.apply_field_query_filters(qs, model, field_tokens)
            qs = self.apply_fts_filter(qs, model, text)
        except Exception:
            LOG.exception("Creating the search filter")

        return qs

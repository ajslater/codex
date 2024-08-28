"""Search Filters Methods."""

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
        # publisher is not really used by my custom match lookup
        #  the MATCH operator actually takes a table as it's left hand side
        #  but django orm doesn't have a facility for that.
        rel = prefix + "comicfts__publisher__match"
        return {rel: text}

    def get_fts_filter(self, model, text):
        """Perform the search and return the scores as a dict."""
        try:
            if text:
                return self._get_fts_filter(model, text)
        except Exception:
            LOG.exception("Getting Full Text Search Filter.")
            self.search_error = True
        return {}

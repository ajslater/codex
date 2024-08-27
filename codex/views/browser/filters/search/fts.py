"""Search Filters Methods."""

from codex.logger.logging import get_logger
from codex.models import Comic, StoryArc
from codex.views.browser.filters.search.field.field import BrowserFieldQueryFilter

LOG = get_logger(__name__)


class BrowserFTSFilter(BrowserFieldQueryFilter):
    """Search Filters Methods."""

    def apply_fts_filter(self, qs, model, text):
        """Perform the search and return the scores as a dict."""
        if not text:
            return qs
        try:
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
            query_dict = {rel: text}
            qs = qs.filter(**query_dict)
            self.fts_mode = True
            self.search_mode = True
        except Exception:
            LOG.exception("Getting Search Scores")
        return qs

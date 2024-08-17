"""Search Filters Methods."""

from codex.logger.logging import get_logger
from codex.models import Comic
from codex.views.browser.filters.search.field import BrowserFieldQueryFilter
from codex.views.const import MAX_OBJ_PER_PAGE

LOG = get_logger(__name__)


class BrowserFTSFilter(BrowserFieldQueryFilter):
    """Search Filters Methods."""

    TARGET = ""

    def _is_search_results_limited(self) -> bool:
        """Get search result limit from params."""
        # user = self.request.user  # type: ignore
        # if user and user.is_authenticated:
        #    limited = bool(
        #        self.params.get(  # type: ignore
        #            "search_results_limit",
        #            MAX_OBJ_PER_PAGE,
        #        )
        #    )
        # else:
        #    limited = True
        # return limited
        return True

    def _limit_search_query(self, qs):
        """Get search scores for choices and metadata."""
        # TODO if we reinvoke this, compine it with _get_common_queryset() limit
        if self._is_search_results_limited():
            page = self.kwargs.get("page", 1)  # type: ignore
            limit = page * MAX_OBJ_PER_PAGE + 1
            qs = qs[:limit]
        return qs

    def apply_fts_filter(self, qs, model, text):
        """Perform the search and return the scores as a dict."""
        if not text:
            return qs
        try:
            prefix = "" if model == Comic else "comic__"
            # HACK publisher not really used by match lookup
            rel = prefix + "comicfts__publisher__match"
            query_dict = {rel: text}
            qs = qs.filter(**query_dict)
            self.fts_mode = True
        except Exception:
            LOG.exception("Getting Search Scores")
        return qs

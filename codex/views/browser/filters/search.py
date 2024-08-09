"""Search Filters Methods."""
from codex.logger.logging import get_logger
from codex.models import Comic
from codex.views.browser.filters.search_field import BrowserQueryParser
from codex.views.const import MAX_OBJ_PER_PAGE

LOG = get_logger(__name__)


class SearchFilterView(BrowserQueryParser):
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

    def _apply_search_filter(self, qs, model, text):
        """Perform the search and return the scores as a dict."""
        if not text:
            return qs
        try:
            prefix = "" if model == Comic else "comic__"
            rel = prefix + "comicfts__body__match"
            qs = qs.filter(**{rel: text})
        except Exception:
            LOG.exception("Getting Search Scores")
        return qs

    def apply_search_filter(self, qs, model):
        """Preparse search, search and return the filter and scores."""
        try:
            qs, text = self.preparse_search_query(qs, model)
            qs = self._apply_search_filter(qs, model, text)
        except Exception:
            LOG.exception("Creating the search filter")

        return qs

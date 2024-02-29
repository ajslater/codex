"""Search Filters Methods."""

from django.db.models import Q

from codex._vendor.haystack.query import SearchQuerySet
from codex.logger.logging import get_logger
from codex.models import Comic

LOG = get_logger(__name__)


class SearchFilterMixin:
    """Search Filters Methods."""

    def get_search_scores(self) -> dict:
        """Perform the search and return the scores as a dict."""
        search_scores = {}
        text = self.params.get("q", "")  # type: ignore
        if not text:
            # for opds 2
            text = self.params.get("query", "")  # type: ignore
        text = text.strip()
        if not text:
            return search_scores

        sqs = SearchQuerySet().auto_query(text)
        comic_scores = sqs.values("pk", "score")
        try:
            for comic_score in comic_scores:
                search_scores[comic_score["pk"]] = comic_score["score"]
        except MemoryError:
            LOG.warning("Search engine needs more memory, results truncated.")
        except Exception:
            LOG.exception("While Searching")
        return search_scores

    def _get_search_query_filter(self, model, search_scores: dict):
        """Get the search filter and scores."""
        prefix = "" if model == Comic else self.rel_prefix  # type: ignore
        rel = prefix + "pk__in"
        query_dict = {rel: search_scores.keys()}
        return Q(**query_dict)

    def get_search_filter(self, model, search_scores: dict):
        """Preparse search, search and return the filter and scores."""
        search_filter = Q()
        try:
            if search_scores:
                # Query haystack
                search_filter = self._get_search_query_filter(model, search_scores)
        except Exception as exc:
            LOG.warning(exc)

        return search_filter

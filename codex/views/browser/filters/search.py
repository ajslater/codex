"""Search Filters Methods."""
from django.db.models import Q
from haystack.query import SearchQuerySet

from codex.logger.logging import get_logger

LOG = get_logger(__name__)


class SearchFilterMixin:
    """Search Filters Methods."""

    def _get_search_scores(self, text, search_scores):
        """Perform the search and return the scores as a dict."""
        sqs = SearchQuerySet().auto_query(text)
        comic_scores = sqs.values("pk", "score")
        try:
            for comic_score in comic_scores:
                search_scores[comic_score["pk"]] = comic_score["score"]
        except MemoryError:
            LOG.warning("Search engine needs more memory, results truncated.")
        except Exception as exc:
            LOG.warning("While searching:")
            LOG.exception(exc)

    def _get_search_query_filter(self, text, search_scores):
        """Get the search filter and scores."""
        rel = self.rel_prefix + "pk__in"  # type: ignore
        self._get_search_scores(text, search_scores)
        query_dict = {rel: search_scores.keys()}
        return Q(**query_dict)

    def get_search_filter(self):
        """Preparse search, search and return the filter and scores."""
        search_filter = Q()
        search_scores = {}
        try:
            query_string = self.params.get("q", "")  # type: ignore
            if not query_string:
                # for opds 2
                query_string = self.params.get("query", "")  # type: ignore

            if query_string:
                # Query haystack
                search_filter = self._get_search_query_filter(
                    query_string, search_scores
                )
        except Exception as exc:
            LOG.warning(exc)

        return search_filter, search_scores

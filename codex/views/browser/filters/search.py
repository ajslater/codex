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

    def _get_search_query_filter(self, text, is_model_comic, search_scores):
        """Get the search filter and scores."""
        # Get search scores
        self._get_search_scores(text, search_scores)

        # Create query
        prefix = ""
        if not is_model_comic:
            prefix = "comic__"
        query_dict = {f"{prefix}pk__in": search_scores.keys()}
        return Q(**query_dict)

    def get_search_filter(self, is_model_comic):
        """Preparse search, search and return the filter and scores."""
        search_filter = Q()
        search_scores = {}
        try:
            query_string = self.params.get("q", "")  # type: ignore

            if query_string:
                # Query haystack
                search_filter = self._get_search_query_filter(
                    query_string, is_model_comic, search_scores
                )
        except Exception as exc:
            LOG.warning(exc)

        return search_filter, search_scores

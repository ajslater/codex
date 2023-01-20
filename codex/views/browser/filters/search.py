"""Search Filters Methods."""
from django.db.models import Q
from haystack.query import SearchQuerySet

from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.librarian.search.tasks import SearchIndexJanitorUpdateTask
from codex.settings.logging import get_logger
from codex.views.browser.filters.search_preparser import SearchFilterPreparserMixin


LOG = get_logger(__name__)


class SearchFilterMixin:  # SearchFilterPreparserMixin):
    """Search Filters Methods."""

    def _get_search_scores(self, text):
        """Perform the search and return the scores as a dict."""
        sqs = SearchQuerySet().auto_query(text)
        comic_scores = sqs.values("pk", "score")
        search_scores = {}
        for comic_score in comic_scores:
            search_scores[comic_score["pk"]] = comic_score["score"]

        search_engine_out_of_date = False
        if search_engine_out_of_date:
            LOG.warning("Search index out of date. Scoring non-existent comics.")
            task = SearchIndexJanitorUpdateTask(False)
            LIBRARIAN_QUEUE.put(task)
        return search_scores

    def _get_search_query_filter(self, text, is_model_comic):
        """Get the search filter and scores."""
        search_filter = Q()
        if not text:
            return search_filter, {}

        # Get search scores
        search_scores = self._get_search_scores(text)

        # Create query
        prefix = ""
        if not is_model_comic:
            prefix = "comic__"
        query_dict = {f"{prefix}pk__in": search_scores.keys()}
        search_filter = Q(**query_dict)

        return search_filter, search_scores

    def get_search_filter(self, is_model_comic):
        """Preparse search, search and return the filter and scores."""
        try:
            # Parse out the bookmark filter and get the remaining tokens
            query_string = self.params.get("q", "")  # type: ignore
            # haystack_text = self._preparse_query_text(query_string)
            haystack_text = query_string

            # Query haystack
            (
                search_filter,
                search_scores,
            ) = self._get_search_query_filter(haystack_text, is_model_comic)
        except Exception as exc:
            LOG.warning(exc)
            search_filter = Q()
            search_scores = {}

        return search_filter, search_scores

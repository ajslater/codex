"""Search Filters Methods."""

from dataclasses import dataclass
from time import time

from django.db.models import Q

from codex._vendor.haystack.query import SearchQuerySet
from codex.logger.logging import get_logger
from codex.models import Comic
from codex.settings.settings import DEBUG
from codex.views.browser.const import MAX_OBJ_PER_PAGE

LOG = get_logger(__name__)


@dataclass
class SearchScores:
    """Search Scores for annotation."""

    scores: tuple[tuple[int, float], ...] = ()
    scored_pks: tuple[int, ...] = ()
    prev_pks: tuple[int, ...] = ()
    next_pks: tuple[int, ...] = ()


class SearchFilterMixin:
    """Search Filters Methods."""

    def _get_binary_search_scores(self, sqs):
        """Get search scores for choices and metadata."""
        sqs = sqs.values_list("pk", flat=True)
        search_results_limit = self.params.get(  # type: ignore
            "search_results_limit",
            MAX_OBJ_PER_PAGE,  # type: ignore
        )
        if search_results_limit:
            sqs = sqs[:search_results_limit]  # type: ignore
        return tuple(sqs)

    def _get_browser_search_scores(self, sqs):
        """Get search scores for the browser cards."""
        page = self.kwargs.get("page", 1)  # type: ignore
        search_results_limit = self.params.get(  # type: ignore
            "search_results_limit",
            MAX_OBJ_PER_PAGE,  # type: ignore
        )
        if search_results_limit:
            offset = 0
            limit = search_results_limit
        else:
            offset = max(0, (page - 1) * MAX_OBJ_PER_PAGE)  # type: ignore
            limit = offset + MAX_OBJ_PER_PAGE  # type: ignore

        if DEBUG:
            LOG.debug(
                f"searching... {page=} page_{offset=} page_{limit=} {search_results_limit=}"
            )

        scores_pairs = []
        prev_pks = []
        next_pks = []

        if DEBUG:
            start_time = time()
        scores_values = sqs.values_list("pk", "score")
        if search_results_limit:
            scores_values = scores_values[:limit]
        for index, pair in enumerate(scores_values):
            if index < offset:
                prev_pks.append(pair[0])
            elif index > limit:
                next_pks.append(pair[0])
            else:
                scores_pairs.append(pair)

        if DEBUG:
            LOG.debug(
                f"search {time() - start_time}s"  # type: ignore
                f" {len(scores_pairs)=} {len(prev_pks)=} {len(next_pks)=}"
            )

        return tuple(scores_pairs), tuple(prev_pks), tuple(next_pks)

    def get_search_scores(self, binary=False) -> SearchScores | None:
        """Perform the search and return the scores as a dict."""
        text = self.params.get("q", "")  # type: ignore
        if not text:
            return None

        scores_pairs = ()
        scored_pks = ()
        prev_pks = ()
        next_pks = ()
        try:
            sqs = SearchQuerySet()
            sqs = sqs.auto_query(text)  # .filter(score__gt=0.0)
            if binary:
                scored_pks = self._get_binary_search_scores(sqs)
            else:
                scores_pairs, prev_pks, next_pks = self._get_browser_search_scores(sqs)

        except MemoryError:
            LOG.warning("Search engine needs more memory, results truncated.")
        except Exception:
            LOG.exception("Getting Search Scores")
        return SearchScores(scores_pairs, scored_pks, prev_pks, next_pks)

    def _get_search_query_filter(
        self,
        model,
        search_scores: SearchScores,
    ):
        """Get the search filter and scores."""
        if search_scores.scores:
            query = Q(search_score__gt=0.0)
        else:
            prefix = "" if model == Comic else self.rel_prefix  # type: ignore
            rel = prefix + "pk__in"
            query_dict = {rel: search_scores.scored_pks}
            query = Q(**query_dict)
        return query

    def apply_search_filter(
        self,
        qs,
        model,
        search_scores: SearchScores | None,
    ):
        """Preparse search, search and return the filter and scores."""
        try:
            if search_scores:
                search_filter = self._get_search_query_filter(model, search_scores)
                qs = qs.filter(search_filter)
        except Exception:
            LOG.exception("Creating the search filter")

        return qs

    def apply_binary_search_filter(self, qs):
        """Apply scoreless search filter for choices & metadata."""
        search_scores = self.get_search_scores(binary=True)
        model = self.model  # type: ignore
        return self.apply_search_filter(qs, model, search_scores)

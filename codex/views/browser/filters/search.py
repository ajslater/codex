"""Search Filters Methods."""

from dataclasses import dataclass
from time import time

from django.db.models import Case, Max, Q, When

from codex.logger.logging import get_logger
from codex.models import Comic
from codex.search.query import CodexSearchQuerySet
from codex.settings.settings import DEBUG
from codex.views.browser.const import MAX_OBJ_PER_PAGE

LOG = get_logger(__name__)
SEARCH_SCORE_MAX = 100.0
SEARCH_SCORE_MIN = 0.001
SEARCH_SCORE_EMPTY = 0.0


@dataclass
class SearchScores:
    """Search Scores for annotation."""

    scores: tuple[tuple[int, float], ...] = ()
    scored_pks: tuple[int, ...] = ()
    prev_pks: tuple[int, ...] = ()
    next_pks: tuple[int, ...] = ()


class SearchFilterMixin:
    """Search Filters Methods."""

    def _is_search_results_limited(self) -> bool:
        """Get search result limit from params."""
        user = self.request.user  # type: ignore
        if user and user.is_authenticated:
            limited = bool(
                self.params.get(  # type: ignore
                    "search_results_limit",
                    MAX_OBJ_PER_PAGE,
                )
            )
        else:
            limited = True
        return limited

    def _get_binary_search_scores(self, sqs):
        """Get search scores for choices and metadata."""
        sqs = sqs.values_list("pk", flat=True)
        if self._is_search_results_limited():
            page = self.kwargs.get("page", 1)  # type: ignore
            limit = page * MAX_OBJ_PER_PAGE + 1
            sqs = sqs[:limit]
        return tuple(sqs)

    def _get_browser_search_scores_params(self, is_search_results_limited):
        page = self.kwargs.get("page", 1)  # type: ignore
        if is_search_results_limited:
            offset = 0
            limit = page * MAX_OBJ_PER_PAGE + 1
        else:
            # For unlimited search actually take a slice
            offset = max(0, (page - 1) * MAX_OBJ_PER_PAGE)  # type: ignore
            limit = offset + MAX_OBJ_PER_PAGE  # type: ignore

        if DEBUG:
            LOG.debug(
                f"Searching... {page=} {offset=} {limit=} {is_search_results_limited=}"
            )
        return offset, limit

    def _get_browser_search_scores(self, sqs):
        """Get search scores for the browser cards."""
        is_search_results_limited = self._is_search_results_limited()
        offset, limit = self._get_browser_search_scores_params(
            is_search_results_limited
        )

        scores_pairs = []
        prev_pks = []
        next_pks = []

        if DEBUG:
            start_time = time()

        order_reverse = self.params.get("order_reverse", False)  # type: ignore
        if not order_reverse:
            sqs = sqs.order_reverse()

        scores_values = sqs.values_list("pk", "score")
        if is_search_results_limited:
            scores_values = scores_values[:limit]
        for index, pair in enumerate(scores_values):
            if index < offset:
                prev_pks.append(pair[0])
            elif index > limit:
                next_pks.append(pair[0])
            else:
                scores_pairs.append(pair)

        if not order_reverse:
            tmp = prev_pks
            prev_pks = next_pks
            next_pks = tmp

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
            sqs = CodexSearchQuerySet()
            sqs = sqs.auto_query(text)  # .filter(score__gt=0.0)

            binary = binary or self.params.get("order_by") != "search_score"  # type: ignore
            if binary:
                scored_pks = self._get_binary_search_scores(sqs)
            else:
                scores_pairs, prev_pks, next_pks = self._get_browser_search_scores(sqs)

        except MemoryError:
            LOG.warning("Search engine needs more memory, results truncated.")
        except Exception:
            LOG.exception("Getting Search Scores")
        return SearchScores(scores_pairs, scored_pks, prev_pks, next_pks)

    def _annotate_search_score(self, qs, model, search_scores: SearchScores | None):
        """Annotate the search score for ordering by search score.

        Choose the maximum matching score for the group.
        """
        whens = []
        prefix = "" if model == Comic else self.rel_prefix  # type: ignore
        if search_scores:
            for pk, score in search_scores.scores:
                when = {prefix + "pk": pk, "then": score}
                whens.append(When(**when))
            if search_scores.prev_pks:
                whens.append(When(pk__in=search_scores.prev_pks, then=SEARCH_SCORE_MAX))
            if search_scores.next_pks:
                whens.append(When(pk__in=search_scores.next_pks, then=SEARCH_SCORE_MIN))
        annotate = {"search_score": Max(Case(*whens, default=SEARCH_SCORE_EMPTY))}
        return qs.annotate(**annotate)

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

    def apply_search_filter(self, qs, model, binary=False):
        """Preparse search, search and return the filter and scores."""
        try:
            search_scores = self.get_search_scores(binary)
            qs = self._annotate_search_score(qs, model, search_scores)
            if search_scores:
                search_filter = self._get_search_query_filter(model, search_scores)
                qs = qs.filter(search_filter)
        except Exception:
            LOG.exception("Creating the search filter")

        return qs

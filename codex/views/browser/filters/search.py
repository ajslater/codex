"""Search Filters Methods."""

from types import MappingProxyType

from django.db.models import Q

from codex._vendor.haystack.query import SearchQuerySet
from codex.logger.logging import get_logger
from codex.models import Comic

LOG = get_logger(__name__)


class SearchFilterMixin:
    """Search Filters Methods."""

    def get_search_scores(
        self, binary=False
    ) -> tuple[MappingProxyType | None, tuple[int, ...] | None, tuple[int, ...] | None]:
        """Perform the search and return the scores as a dict."""
        text = self.params.get("q", "")  # type: ignore
        if not text:
            # for opds 2
            text = self.params.get("query", "")  # type: ignore
        text = text.strip()
        if not text:
            return MappingProxyType({}), (), ()

        search_scores = None
        search_prev_page_pks = ()
        search_next_page_pks = ()
        try:
            # start_time = time()
            page = self.kwargs.get("page", 1)  # type: ignore
            sqs = SearchQuerySet().auto_query(text)
            comic_scores = sqs.values("pk", "score")
            if not binary:
                limit = page * self.MAX_OBJ_PER_PAGE  # type: ignore
                next_comic_scores = comic_scores[limit:]
                search_next_page_pks = tuple(score["pk"] for score in next_comic_scores)
                offset = (page - 1) * self.MAX_OBJ_PER_PAGE  # type: ignore
                prev_comic_scores = comic_scores[:offset]
                search_prev_page_pks = tuple(score["pk"] for score in prev_comic_scores)
                comic_scores = comic_scores[offset:limit]
                # print(f"{offset=} {limit=} {len(comic_scores)=} {len(search_prev_page_pks)=} {len(search_next_page_pks)=}")
            search_scores = MappingProxyType(
                {score["pk"]: score["score"] for score in comic_scores}
            )
            # print(f"Map Scores {time() - start_time}")
        except MemoryError:
            LOG.warning("Search engine needs more memory, results truncated.")
        except Exception:
            LOG.exception("While Searching")
        if not search_scores:
            # in case search scores is {}
            return None, (), ()
        return search_scores, search_prev_page_pks, search_next_page_pks

    def _get_search_query_filter(
        self,
        model,
        search_scores: MappingProxyType,
        search_out_of_page_pks: tuple[int, ...],
    ):
        """Get the search filter and scores."""
        prefix = "" if model == Comic else self.rel_prefix  # type: ignore
        rel = prefix + "pk__in"
        pks = tuple(tuple(search_scores.keys()) + search_out_of_page_pks)
        # print(f"search query filter {len(search_scores.keys())=} {len(search_out_of_page_pks)=} {len(pks)=}")
        query_dict = {rel: pks}
        return Q(**query_dict)

    def get_search_filter(
        self,
        model,
        search_scores: MappingProxyType | None,
        search_out_of_page_pks: tuple[int, ...],
    ):
        """Preparse search, search and return the filter and scores."""
        search_filter = Q()
        try:
            if search_scores:
                # Query haystack
                search_filter = self._get_search_query_filter(
                    model, search_scores, search_out_of_page_pks
                )
        except Exception as exc:
            LOG.warning(exc)

        return search_filter

"""Custom Codex search query classes."""

from codex._vendor.haystack.backends.whoosh_backend import (
    WhooshSearchQuery,
)
from codex._vendor.haystack.constants import DJANGO_ID
from codex._vendor.haystack.query import SearchQuerySet


class CodexSearchQuery(WhooshSearchQuery):
    """Custom search qeuery."""

    def __init__(self, *args, **kwargs):
        """Give CodexSearchQuery a reverse attribute."""
        super().__init__(*args, **kwargs)
        self._reverse: bool = False
        self._filter_comic_ids: frozenset | None = None

    def clean(self, query_fragment):
        """Optimize to noop because RESERVED_ consts are empty in the backend."""
        return query_fragment

    def order_reverse(self):
        """Invert the reverse attribute."""
        self._reverse = not self._reverse

    def filter_comic_ids(self, ids):
        """Set a filter for the query."""
        self._filter_comic_ids = frozenset(ids)

    def get_results(self, **kwargs):
        """Send custom get results the reverse flag."""
        custom_params = {}
        if self._reverse:
            custom_params["reverse"] = self._reverse

        if self._filter_comic_ids:
            filter_query = " OR ".join(
                [f"{DJANGO_ID}:{pk}" for pk in self._filter_comic_ids]
            )
            custom_params["narrow_queries"] = {filter_query}

        return super().get_results(**custom_params, **kwargs)


class CodexSearchQuerySet(SearchQuerySet):
    """SearchQuerySet with order_reverse method."""

    def order_reverse(self):
        """Alters the order in which the results should appear."""
        clone = self._clone()
        clone.query.order_reverse()  # type: ignore
        return clone

    def filter_comic_ids(self, ids):
        """Filter search by comic ids."""
        clone = self._clone()
        clone.query.filter_comic_ids(ids)  # type: ignore
        return clone

    def values_list(self, *args, **kwargs):
        """Copy reverse setting into CodexSearchQuery."""
        clone = super().values_list(*args, **kwargs)
        if clone.query and self.query:
            clone.query._reverse = self.query._reverse  # noqa: SLF001
            clone.query._filter_comic_ids = self.query._filter_comic_ids  # noqa: SLF001
        return clone

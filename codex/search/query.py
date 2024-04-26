"""Custom Codex search query classes."""

from codex._vendor.haystack.backends.whoosh_backend import (
    WhooshSearchQuery,
)
from codex._vendor.haystack.query import SearchQuerySet


class CodexSearchQuery(WhooshSearchQuery):
    """Custom search qeuery."""

    def __init__(self, *args, **kwargs):
        """Give CodexSearchQuery a reverse attribute."""
        super().__init__(*args, **kwargs)
        self._reverse = False

    def clean(self, query_fragment):
        """Optimize to noop because RESERVED_ consts are empty in the backend."""
        return query_fragment

    def order_reverse(self):
        """Invert the reverse attribute."""
        self._reverse = not self._reverse

    def get_results(self, **kwargs):
        """Send custom get results the reverse flag."""
        return super().get_results(reverse=self._reverse, **kwargs)


class CodexSearchQuerySet(SearchQuerySet):
    """SearchQuerySet with order_reverse method."""

    def order_reverse(self):
        """Alters the order in which the results should appear."""
        clone = self._clone()
        clone.query.order_reverse()  # type: ignore
        return clone

    def values_list(self, *args, **kwargs):
        """Copy reverse setting into CodexSearchQuery."""
        clone = super().values_list(*args, **kwargs)
        if clone.query and self.query:
            clone.query._reverse = self.query._reverse  # noqa: SLF001
        return clone

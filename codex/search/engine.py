"""Custom Haystack Search Engine."""
from haystack.backends import UnifiedIndex
from haystack.backends.whoosh_backend import WhooshEngine, WhooshSearchQuery

from codex.search.backend import CodexSearchBackend
from codex.search.indexes import ComicIndex


class CodexUnifiedIndex(UnifiedIndex):
    """Custom Codex Unified Index."""

    def collect_indexes(self):
        """Replace auto app.search_index finding with one exact instance."""
        # Because i moved search_indexes into codex.search
        return [ComicIndex()]


class CodexSearchQuery(WhooshSearchQuery):
    """Custom search qeuery."""

    def clean(self, query_fragment):
        """Optimize to noop because RESERVED_ consts are empty in the backend."""
        return query_fragment


class CodexSearchEngine(WhooshEngine):
    """A search engine with a locking backend."""

    backend = CodexSearchBackend
    query = CodexSearchQuery
    unified_index = CodexUnifiedIndex

    def __init__(self, using=None, queue_kwargs=None):
        """Initialize options with queue kwargs."""
        super().__init__(using=using)
        if not queue_kwargs:
            queue_kwargs = {}
        self.options.update(queue_kwargs)

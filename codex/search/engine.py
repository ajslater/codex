"""Custom Haystack Search Engine."""

from codex._vendor.haystack.backends import UnifiedIndex
from codex._vendor.haystack.backends.whoosh_backend import (
    WhooshEngine,
)
from codex.search.backend import CodexSearchBackend
from codex.search.indexes import ComicIndex
from codex.search.query import CodexSearchQuery


class CodexUnifiedIndex(UnifiedIndex):
    """Custom Codex Unified Index."""

    def collect_indexes(self):
        """Replace auto app.search_index finding with one exact instance."""
        # Because I moved search_indexes into codex.search
        return [ComicIndex()]


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

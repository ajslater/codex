"""Libarian Tasks for searchd."""

from dataclasses import dataclass

from codex.librarian.scribe.tasks import ScribeTask


class SearchIndexerTask(ScribeTask):
    """Tasks for the search indexer."""


@dataclass
class SearchIndexSyncTask(SearchIndexerTask):
    """Update the search index."""

    rebuild: bool = False


class SearchIndexOptimizeTask(SearchIndexerTask):
    """Optimize search index."""


class SearchIndexCleanStaleTask(SearchIndexerTask):
    """Remove stale records."""


class SearchIndexClearTask(SearchIndexerTask):
    """Clear current search index."""

"""Libarian Tasks for searchd."""

from dataclasses import dataclass


@dataclass
class SearchIndexerTask:
    """Tasks for the search indexer."""


@dataclass
class SearchIndexUpdateTask(SearchIndexerTask):
    """Update the search index."""

    rebuild: bool


@dataclass
class SearchIndexRemoveStaleTask(SearchIndexerTask):
    """Remove stale records."""


@dataclass
class SearchIndexAbortTask(SearchIndexerTask):
    """Abort current search index."""


@dataclass
class SearchIndexClearTask(SearchIndexerTask):
    """Clear current search index."""

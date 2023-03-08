"""Libarian Tasks for searchd."""
from dataclasses import dataclass


@dataclass
class SearchIndexerTask:
    """Tasks for the search indexer."""

    pass


@dataclass
class SearchIndexRebuildIfDBChangedTask(SearchIndexerTask):
    """Task to check if the db is changed and schedule an update task."""

    pass


@dataclass
class SearchIndexUpdateTask(SearchIndexerTask):
    """Update the search index."""

    rebuild: bool


@dataclass
class SearchIndexMergeTask(SearchIndexerTask):
    """Merge a fragmented index."""

    optimize: bool = False


@dataclass
class SearchIndexRemoveStaleTask(SearchIndexerTask):
    """Remove stale records."""

    pass

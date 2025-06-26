"""DB Import Tasks."""

from dataclasses import dataclass
from datetime import datetime


class ScribeTask:
    """Tasks for scribed."""


@dataclass
class UpdateGroupsTask(ScribeTask):
    """Force the update of group timestamp."""

    start_time: datetime | None = None


@dataclass
class LazyImportComicsTask(ScribeTask):
    """Lazy import of metadaa for existing comics."""

    group: str
    pks: frozenset[int]


class ImportAbortTask(ScribeTask):
    """Abort Import."""


class SearchIndexAbortTask(ScribeTask):
    """Abort current search index."""

"""DB Import Tasks."""

from abc import ABC
from dataclasses import dataclass
from datetime import datetime


class ScribeTask(ABC):  # noqa: B024
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


class SearchIndexSyncAbortTask(ScribeTask):
    """Abort current search index sync."""

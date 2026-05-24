"""DB Import Tasks."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from codex.librarian.tasks import LibrarianTask


class ScribeTask(LibrarianTask):
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


@dataclass
class ForceUpdateComicsTask(ScribeTask):
    """Force a metadata re-import for a specific set of comic pks."""

    comic_pks: frozenset[int]


@dataclass
class BulkTagWriteTask(ScribeTask):
    """Write tags to comic archives via comicbox.bulk_write."""

    comic_pks: frozenset[int]
    mode: str = "update"
    formats: tuple[str, ...] = ("COMIC_INFO",)
    patch: dict[str, Any] | None = None
    per_comic_patches: dict[int, dict[str, Any]] = field(default_factory=dict)


class TagWriteAbortTask(ScribeTask):
    """Abort a running tag-write batch."""


class ImportAbortTask(ScribeTask):
    """Abort Import."""


class SearchIndexSyncAbortTask(ScribeTask):
    """Abort current search index sync."""


class CleanupAbortTask(ScribeTask):
    """Abort running cleanup/janitor tasks."""

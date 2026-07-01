"""DB Import Tasks."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from codex.librarian.tasks import LibrarianTask


class ScribeTask(LibrarianTask):
    """Tasks for scribed."""


@dataclass
class UpdateCollectionsTask(ScribeTask):
    """Force the update of collection timestamp."""

    start_time: datetime | None = None


@dataclass
class LazyImportComicsTask(ScribeTask):
    """Lazy import of metadaa for existing comics."""

    collection: str
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
    delete_original: bool = False
    patch: dict[str, Any] | None = None
    per_comic_patches: dict[int, dict[str, Any]] = field(default_factory=dict)
    # When True, rename each written archive to the comicbox (comicfn2dict)
    # filename scheme after its tags are written. With no patch (rename-only),
    # every resolved comic is renamed from its existing on-archive metadata.
    rename: bool = False


class TagWriteAbortTask(ScribeTask):
    """Abort a running tag-write batch."""


class ImportAbortTask(ScribeTask):
    """Abort Import."""


class SearchIndexSyncAbortTask(ScribeTask):
    """Abort current search index sync."""


class CleanupAbortTask(ScribeTask):
    """Abort running cleanup/janitor tasks."""

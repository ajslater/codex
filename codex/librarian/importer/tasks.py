"""DB Import Tasks."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ImportTask:
    """Tasks for the updater."""


@dataclass
class ImportDBDiffTask(ImportTask):
    """For sending to the updater."""

    library_id: int

    dirs_moved: Mapping[str, str] = field(default_factory=dict)
    dirs_modified: frozenset[str] = frozenset()
    # dirs_created: frozenset[str] | None = frozenset()
    dirs_deleted: frozenset[str] = frozenset()

    files_moved: Mapping[str, str] = field(default_factory=dict)
    files_modified: frozenset[str] = frozenset()
    files_created: frozenset[str] = frozenset()
    files_deleted: frozenset[str] = frozenset()

    covers_moved: Mapping[str, str] = field(default_factory=dict)
    covers_modified: frozenset[str] = frozenset()
    covers_created: frozenset[str] = frozenset()
    covers_deleted: frozenset[str] = frozenset()

    force_import_metadata: bool = False


@dataclass
class LazyImportComicsTask(ImportTask):
    """Lazy import of metadaa for existing comics."""

    pks: frozenset[int]


@dataclass
class AdoptOrphanFoldersTask(ImportTask):
    """Move orphaned folders into a correct tree position."""

    janitor: bool = False


@dataclass
class UpdateGroupsTask(ImportTask):
    """Force the update of group timestamp."""

    start_time: datetime | None = None

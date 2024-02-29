"""DB Import Tasks."""

from dataclasses import dataclass


@dataclass
class ImportTask:
    """Tasks for the updater."""


@dataclass
class ImportDBDiffTask(ImportTask):
    """For sending to the updater."""

    library_id: int
    dirs_moved: dict[str, str]
    files_moved: dict[str, str]
    dirs_modified: frozenset[str]
    files_modified: frozenset[str]
    # dirs_created
    files_created: frozenset[str]
    dirs_deleted: frozenset[str]
    files_deleted: frozenset[str]


@dataclass
class AdoptOrphanFoldersTask(ImportTask):
    """Move orphaned folders into a correct tree position."""

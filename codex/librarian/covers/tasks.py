"""Covers Tasks."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CoverTask:
    """Handle with the CoverCreator."""

    pass


@dataclass
class CoverCreateTask(CoverTask):
    """Create one comic cover."""

    path: Path
    data: bytes


@dataclass
class CoverBulkCreateTask(CoverTask):
    """A list of comic src and dest paths."""

    comic_pks: frozenset


@dataclass
class CoverRemoveAllTask(CoverTask):
    """Remove all comic covers."""

    pass


@dataclass
class CoverRemoveOrphansTask(CoverTask):
    """Clean up covers from missing comics."""

    pass


@dataclass
class LibrariesTask:
    """Tasks over a set of libraries."""

    library_ids: frozenset


# TODO look if obsolete
@dataclass
class CoverRemoveTask(CoverTask):
    """Purge a set of comic covers."""

    comic_pks: frozenset

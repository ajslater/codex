"""Covers Tasks."""

from dataclasses import dataclass

from codex.librarian.tasks import LibrarianTask


class CoverTask(LibrarianTask):
    """Handle with the CoverThread."""


class CoverRemoveAllTask(CoverTask):
    """Remove all comic covers."""


class CoverRemoveOrphansTask(CoverTask):
    """Clean up covers from missing comics."""


@dataclass
class CoverRemoveTask(CoverTask):
    """Purge a set of comic covers."""

    pks: frozenset
    custom: bool


@dataclass
class CoverSaveToCache(CoverTask):
    """Write cover to disk."""

    cover_path: str
    data: bytes


class CoverCreateAllTask(CoverTask):
    """A create all comic covers."""


@dataclass
class CoverCreateTask(CoverTask):
    """Create covers for a specific set of pks."""

    pks: tuple
    custom: bool

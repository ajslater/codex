"""Covers Tasks."""

from dataclasses import dataclass

from codex.librarian.tasks import LibrarianTask


@dataclass
class CoverTask(LibrarianTask):
    """Handle with the CoverThread."""


@dataclass
class CoverRemoveAllTask(CoverTask):
    """Remove all comic covers."""


@dataclass
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


@dataclass
class CoverCreateAllTask(CoverTask):
    """A create all comic covers."""

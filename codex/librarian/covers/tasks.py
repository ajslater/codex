"""Covers Tasks."""

from dataclasses import dataclass


@dataclass
class CoverTask:
    """Handle with the CoverContributor."""


@dataclass
class CoverRemoveAllTask(CoverTask):
    """Remove all comic covers."""


@dataclass
class CoverRemoveOrphansTask(CoverTask):
    """Clean up covers from missing comics."""


@dataclass
class LibrariesTask:
    """Tasks over a set of libraries."""

    library_ids: frozenset


@dataclass
class CoverRemoveTask(CoverTask):
    """Purge a set of comic covers."""

    comic_pks: frozenset


@dataclass
class CoverSaveToCache(CoverTask):
    """Write cover to disk."""

    cover_path: str
    data: bytes


@dataclass
class CoverCreateAllTask(CoverTask):
    """A create all comic covers."""

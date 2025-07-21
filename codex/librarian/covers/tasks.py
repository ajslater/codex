"""Covers Tasks."""

from abc import ABC
from dataclasses import dataclass


@dataclass
class CoverTask(ABC):  # noqa: B024
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

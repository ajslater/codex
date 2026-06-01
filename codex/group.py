"""
The canonical browse-group vocabulary.

Codex browses comics by group: publishers, imprints, series, volumes,
issues, folders and story arcs, plus a synthetic *root* level that
defers to the user's top-group setting. A group is identified two ways:
a plural collection name (``"publishers"``) in the engine, DB, OPDS and
v4 API/URLs, and a singular name (``"publisher"``) for cover filenames.

:class:`Group` is the single source of truth that ties those
representations together.

The member *value* is the v4 **collection name** (``"publishers"``,
``"series"``, …; ``ROOT`` resolves to ``"root"``). A ``StrEnum`` member
compares and hashes equal to its value, so a dict re-keyed to ``Group``
members is found by a collection-name lookup — which is how the engine,
the DB and the URLConf speak one vocabulary end to end.

This module is intentionally dependency-free (no Django/model imports)
so it can be imported from anywhere — models, views, serializers,
URLConf — without import-cycle risk.
"""

from enum import StrEnum
from types import MappingProxyType
from typing import Final


class Group(StrEnum):
    """A browsable group. The member value is the v4 collection name."""

    ROOT = "root"  # synthetic top level; resolves to its top collection in URLs
    PUBLISHER = "publishers"
    IMPRINT = "imprints"
    SERIES = "series"
    VOLUME = "volumes"
    COMIC = "comics"
    FOLDER = "folders"
    ARC = "arcs"

    @classmethod
    def from_collection(cls, collection: str) -> "Group":
        """Resolve a v4 collection name to its member."""
        return GROUP_BY_COLLECTION[collection]

    @property
    def collection(self) -> str:
        """The v4 collection name for this group (ROOT has none of its own)."""
        return GROUP_COLLECTIONS[self]


# Group → v4 collection name. ROOT is excluded: it is not a URL collection
# of its own; the route boundary resolves it to its top collection.
GROUP_COLLECTIONS: Final[MappingProxyType[Group, str]] = MappingProxyType(
    {
        Group.PUBLISHER: "publishers",
        Group.IMPRINT: "imprints",
        Group.SERIES: "series",
        Group.VOLUME: "volumes",
        Group.COMIC: "comics",
        Group.FOLDER: "folders",
        Group.ARC: "arcs",
    }
)
GROUP_BY_COLLECTION: Final[MappingProxyType[str, Group]] = MappingProxyType(
    {collection: group for group, collection in GROUP_COLLECTIONS.items()}
)

# Group → singular name, used only for cover / placeholder filenames
# (``img/publisher.svg``). ROOT has no cover of its own.
GROUP_SINGULAR_NAMES: Final[MappingProxyType[Group, str]] = MappingProxyType(
    {
        Group.PUBLISHER: "publisher",
        Group.IMPRINT: "imprint",
        Group.SERIES: "series",
        Group.VOLUME: "volume",
        Group.COMIC: "comic",
        Group.FOLDER: "folder",
        Group.ARC: "story-arc",
    }
)

# Group → human display label (UI / OPDS choices). COMIC reads as
# "Issues" to match comic-reader convention. ROOT is not user-selectable.
GROUP_LABELS: Final[MappingProxyType[Group, str]] = MappingProxyType(
    {
        Group.PUBLISHER: "Publishers",
        Group.IMPRINT: "Imprints",
        Group.SERIES: "Series",
        Group.VOLUME: "Volumes",
        Group.COMIC: "Issues",
        Group.FOLDER: "Folders",
        Group.ARC: "Story Arcs",
    }
)

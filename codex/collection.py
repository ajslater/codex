"""
The canonical browse-collection vocabulary.

Codex browses comics by collection: publishers, imprints, series, volumes,
issues, folders and story arcs, plus a synthetic *root* level that
defers to the user's top-collection setting. A collection is identified two ways:
a plural collection name (``"publishers"``) in the engine, DB, OPDS and
v4 API/URLs, and a singular name (``"publisher"``) for cover filenames.

:class:`Collection` is the single source of truth that ties those
representations together.

The member *value* is the v4 **collection name** (``"publishers"``,
``"series"``, …; ``ROOT`` resolves to ``"root"``). A ``StrEnum`` member
compares and hashes equal to its value, so a dict re-keyed to ``Collection``
members is found by a collection-name lookup — which is how the engine,
the DB and the URLConf speak one vocabulary end to end.

This module is intentionally dependency-free (no Django/model imports)
so it can be imported from anywhere — models, views, serializers,
URLConf — without import-cycle risk.
"""

from enum import StrEnum
from types import MappingProxyType
from typing import Final


class Collection(StrEnum):
    """A browsable collection. The member value is the v4 collection name."""

    ROOT = "root"  # synthetic top level; resolves to its top collection in URLs
    PUBLISHER = "publishers"
    IMPRINT = "imprints"
    SERIES = "series"
    VOLUME = "volumes"
    COMIC = "comics"
    FOLDER = "folders"
    ARC = "arcs"

    @classmethod
    def from_collection(cls, collection: str) -> "Collection":
        """Resolve a v4 collection name to its member."""
        return COLLECTION_BY_NAME[collection]

    @property
    def collection(self) -> str:
        """The v4 collection name for this collection (ROOT has none of its own)."""
        return COLLECTION_NAMES[self]


# Collection → v4 collection name. ROOT is excluded: it is not a URL collection
# of its own; the route boundary resolves it to its top collection.
COLLECTION_NAMES: Final[MappingProxyType[Collection, str]] = MappingProxyType(
    {
        Collection.PUBLISHER: "publishers",
        Collection.IMPRINT: "imprints",
        Collection.SERIES: "series",
        Collection.VOLUME: "volumes",
        Collection.COMIC: "comics",
        Collection.FOLDER: "folders",
        Collection.ARC: "arcs",
    }
)
COLLECTION_BY_NAME: Final[MappingProxyType[str, Collection]] = MappingProxyType(
    {name: collection for collection, name in COLLECTION_NAMES.items()}
)

# Collection → singular name, used only for cover / placeholder filenames
# (``img/publisher.svg``). ROOT has no cover of its own.
COLLECTION_SINGULAR_NAMES: Final[MappingProxyType[Collection, str]] = MappingProxyType(
    {
        Collection.PUBLISHER: "publisher",
        Collection.IMPRINT: "imprint",
        Collection.SERIES: "series",
        Collection.VOLUME: "volume",
        Collection.COMIC: "comic",
        Collection.FOLDER: "folder",
        Collection.ARC: "story-arc",
    }
)

# Collection → human display label (UI / OPDS choices). COMIC reads as
# "Issues" to match comic-reader convention. ROOT is not user-selectable.
COLLECTION_LABELS: Final[MappingProxyType[Collection, str]] = MappingProxyType(
    {
        Collection.PUBLISHER: "Publishers",
        Collection.IMPRINT: "Imprints",
        Collection.SERIES: "Series",
        Collection.VOLUME: "Volumes",
        Collection.COMIC: "Issues",
        Collection.FOLDER: "Folders",
        Collection.ARC: "Story Arcs",
    }
)

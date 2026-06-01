"""
The canonical browse-group vocabulary.

Codex browses comics by group: publishers, imprints, series, volumes,
issues, folders and story arcs, plus a synthetic *root* level that
defers to the user's top-group setting. Historically each group was
identified three different ways — a single-char code (``"p"``) in the
engine, DB and OPDS; a singular name (``"publisher"``) for cover
filenames; and a plural collection name (``"publishers"``) in the v4
API and URLs.

:class:`Group` is the single source of truth that ties those
representations together.

The member *value* is the v4 **collection name** (``"publishers"``,
``"series"``, …; ``ROOT`` resolves to ``"root"``). A ``StrEnum`` member
compares and hashes equal to its value, so a dict re-keyed to ``Group``
members is found by a collection-name lookup — which is how the engine,
the DB and the URLConf now speak one vocabulary end to end.

The values were *previously* the legacy single-char codes during the
migration; they were flipped to collection names once every layer
adopted the enum. The whole app now speaks collection end to end. The
only legacy-char machinery that survives is :data:`GROUP_CHARS` /
:data:`GROUP_BY_CHAR`, kept solely so :func:`group_value` can normalize
a char read from a *legacy* ``user_data`` backup sidecar back to its
collection value on restore. No live code emits char anymore.

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


# Group → legacy single-char code. Held explicitly (not derived from the
# member value, which is now the collection name). Retained solely so
# :func:`group_value` can normalize a char read from a *legacy* user_data
# backup sidecar back to its collection value on restore; no live code emits
# char anymore.
GROUP_CHARS: Final[MappingProxyType[Group, str]] = MappingProxyType(
    {
        Group.ROOT: "r",
        Group.PUBLISHER: "p",
        Group.IMPRINT: "i",
        Group.SERIES: "s",
        Group.VOLUME: "v",
        Group.COMIC: "c",
        Group.FOLDER: "f",
        Group.ARC: "a",
    }
)
GROUP_BY_CHAR: Final[MappingProxyType[str, Group]] = MappingProxyType(
    {char: group for group, char in GROUP_CHARS.items()}
)

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
# Member value (collection name, incl. ROOT="root") → Group. ``Group(value)``
# is equivalent but raises on a char; this map + the helpers below are tolerant.
_GROUP_BY_VALUE: Final[MappingProxyType[str, Group]] = MappingProxyType(
    {group.value: group for group in Group}
)


def group_value(value: str) -> str:
    """
    Return the collection value for a group — the char→collection direction.

    Idempotent: accepts either a char (``"p"``, ``"r"``) or a collection
    value and returns the collection value (``"publishers"``, ``"root"``).
    Unknown values pass through unchanged.
    """
    group = GROUP_BY_CHAR.get(value) or _GROUP_BY_VALUE.get(value)
    return group.value if group else value


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

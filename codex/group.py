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
adopted the enum. ``.char`` survives that flip (it reads
:data:`GROUP_CHARS` below, not the member value) and still serves the
few legacy char surfaces that remain: the frontend's char wire dialect
(translated at the serializer edge), ``app.py``'s legacy
``<group:group>`` route, and ``Favorite``'s char codes.

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
    def from_char(cls, char: str) -> "Group":
        """Resolve a legacy single-char group code to its member."""
        return GROUP_BY_CHAR[char]

    @classmethod
    def from_collection(cls, collection: str) -> "Group":
        """Resolve a v4 collection name to its member."""
        return GROUP_BY_COLLECTION[collection]

    @property
    def char(self) -> str:
        """The legacy single-char code for this group."""
        return GROUP_CHARS[self]

    @property
    def collection(self) -> str:
        """The v4 collection name for this group (ROOT has none of its own)."""
        return GROUP_COLLECTIONS[self]


# Group → legacy single-char code. Held explicitly (not derived from the
# member value, which is now the collection name) so the few remaining char
# surfaces — the frontend wire dialect, app.py's legacy route, Favorite — keep
# resolving across the value flip.
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


def group_char(value: str) -> str:
    """
    Return the char code for a group value — the collection→char direction.

    Idempotent: accepts either a collection value (``"publishers"``,
    ``"root"``) or a char (``"p"``, ``"r"``) and returns the char.
    Unknown values pass through unchanged.
    """
    group = _GROUP_BY_VALUE.get(value) or GROUP_BY_CHAR.get(value)
    return group.char if group else value


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

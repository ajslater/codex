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

The member *value* is, for now, the legacy single-char code. This is a
deliberate transition choice: a ``StrEnum`` member compares and hashes
equal to its value, so while the value is the char the enum is a
drop-in for the char strings still threaded through the engine, the DB
and the URLConf — a dict re-keyed to ``Group`` members is still found
by the old char keys, letting each layer adopt the enum incrementally
with no behavior change. The migration's end state flips these values
to the v4 collection names; ``.char`` and ``.collection`` keep working
across that flip because they read the explicit maps below rather than
the member value.

This module is intentionally dependency-free (no Django/model imports)
so it can be imported from anywhere — models, views, serializers,
URLConf — without import-cycle risk.
"""

from enum import StrEnum
from types import MappingProxyType
from typing import Final


class Group(StrEnum):
    """A browsable group. The member value is the legacy single-char code."""

    ROOT = "r"  # synthetic top level; resolves to its top collection in URLs
    PUBLISHER = "p"
    IMPRINT = "i"
    SERIES = "s"
    VOLUME = "v"
    COMIC = "c"
    FOLDER = "f"
    ARC = "a"

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


# Group → legacy single-char code (engine kwargs, DB columns, OPDS).
# Held explicitly — not derived from the member value — so it survives the
# eventual flip of member values to collection names.
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

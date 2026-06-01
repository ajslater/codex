"""Unit tests for the canonical browse-group vocabulary."""

from typing import Final

from codex.group import (
    GROUP_BY_CHAR,
    GROUP_BY_COLLECTION,
    GROUP_CHARS,
    GROUP_COLLECTIONS,
    GROUP_LABELS,
    GROUP_SINGULAR_NAMES,
    Group,
)

# The seven groups that are real v4 URL collections (everything but ROOT).
_COLLECTIONS: Final = frozenset(
    {
        "publishers",
        "imprints",
        "series",
        "volumes",
        "comics",
        "folders",
        "arcs",
    }
)


def test_value_is_collection_name():
    """A member's value is its v4 collection name (ROOT → ``"root"``)."""
    assert Group.PUBLISHER == "publishers"
    assert Group.ROOT == "root"
    assert {g.value for g in Group} == _COLLECTIONS | {"root"}


def test_strenum_interop_with_collections():
    """
    Members are interchangeable with their collection-name value.

    Equality *and* hashing match, so a dict re-keyed to Group members is found
    by the collection-name string — the property that lets the engine, DB and
    URLConf speak one vocabulary end to end after the value flip.
    """
    assert Group.SERIES == "series"
    assert hash(Group.SERIES) == hash("series")
    # Typed dict[str, str] because Group is a str subtype; the point is that
    # member and collection keys resolve to the same bucket at runtime.
    sample: dict[str, str] = {Group.SERIES: "x"}
    assert sample["series"] == "x"
    sample_by_collection: dict[str, str] = {"series": "y"}
    assert sample_by_collection[Group.SERIES] == "y"


def test_char_round_trip():
    """Every group round-trips through its legacy single-char code."""
    for group in Group:
        assert Group.from_char(group.char) is group
    assert Group.from_char("r") is Group.ROOT


def test_collection_round_trip():
    """Every non-root group round-trips through its v4 collection name."""
    for group in Group:
        if group is Group.ROOT:
            continue
        assert Group.from_collection(group.collection) is group
    assert {g.collection for g in GROUP_COLLECTIONS} == _COLLECTIONS


def test_chars_are_unique_and_complete():
    """Every member has a char; chars are the historical single letters."""
    assert set(GROUP_CHARS) == set(Group)
    assert set(GROUP_BY_CHAR) == set("rpisvcfa")
    assert len(GROUP_BY_CHAR) == len(Group)


def test_root_excluded_from_collection_only_maps():
    """ROOT is synthetic: it has a char but no collection, cover, or label."""
    assert Group.ROOT in GROUP_CHARS
    for only_real in (
        GROUP_COLLECTIONS,
        GROUP_BY_COLLECTION,
        GROUP_SINGULAR_NAMES,
        GROUP_LABELS,
    ):
        assert Group.ROOT not in only_real
    assert set(GROUP_COLLECTIONS) == set(Group) - {Group.ROOT}
    assert set(GROUP_SINGULAR_NAMES) == set(Group) - {Group.ROOT}
    assert set(GROUP_LABELS) == set(Group) - {Group.ROOT}


def test_known_representations():
    """Pin the legacy-sensitive representations that other layers rely on."""
    assert Group.COMIC.char == "c"
    assert Group.COMIC.collection == "comics"
    assert Group.PUBLISHER.collection == "publishers"
    # COMIC's display label is the reader-convention "Issues", not "Comics".
    assert GROUP_LABELS[Group.COMIC] == "Issues"
    # Cover filename for arcs is hyphenated.
    assert GROUP_SINGULAR_NAMES[Group.ARC] == "story-arc"

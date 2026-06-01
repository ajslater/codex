"""Unit tests for the canonical browse-group vocabulary."""

from typing import Final

from codex.collection import (
    COLLECTION_BY_NAME,
    COLLECTION_LABELS,
    COLLECTION_NAMES,
    COLLECTION_SINGULAR_NAMES,
    Collection,
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
    assert Collection.PUBLISHER == "publishers"
    assert Collection.ROOT == "root"
    assert {g.value for g in Collection} == _COLLECTIONS | {"root"}


def test_strenum_interop_with_collections():
    """
    Members are interchangeable with their collection-name value.

    Equality *and* hashing match, so a dict re-keyed to Collection members is found
    by the collection-name string — the property that lets the engine, DB and
    URLConf speak one vocabulary end to end after the value flip.
    """
    assert Collection.SERIES == "series"
    assert hash(Collection.SERIES) == hash("series")
    # Typed dict[str, str] because Collection is a str subtype; the point is that
    # member and collection keys resolve to the same bucket at runtime.
    sample: dict[str, str] = {Collection.SERIES: "x"}
    assert sample["series"] == "x"
    sample_by_collection: dict[str, str] = {"series": "y"}
    assert sample_by_collection[Collection.SERIES] == "y"


def test_collection_round_trip():
    """Every non-root group round-trips through its v4 collection name."""
    for group in Collection:
        if group is Collection.ROOT:
            continue
        assert Collection.from_collection(group.collection) is group
    assert {g.collection for g in COLLECTION_NAMES} == _COLLECTIONS


def test_root_excluded_from_collection_only_maps():
    """ROOT is synthetic: no collection, cover, or label of its own."""
    for only_real in (
        COLLECTION_NAMES,
        COLLECTION_BY_NAME,
        COLLECTION_SINGULAR_NAMES,
        COLLECTION_LABELS,
    ):
        assert Collection.ROOT not in only_real
    assert set(COLLECTION_NAMES) == set(Collection) - {Collection.ROOT}
    assert set(COLLECTION_SINGULAR_NAMES) == set(Collection) - {Collection.ROOT}
    assert set(COLLECTION_LABELS) == set(Collection) - {Collection.ROOT}


def test_known_representations():
    """Pin the representations that other layers rely on."""
    assert Collection.COMIC.collection == "comics"
    assert Collection.PUBLISHER.collection == "publishers"
    # COMIC's display label is the reader-convention "Issues", not "Comics".
    assert COLLECTION_LABELS[Collection.COMIC] == "Issues"
    # Cover filename for arcs is hyphenated.
    assert COLLECTION_SINGULAR_NAMES[Collection.ARC] == "story-arc"

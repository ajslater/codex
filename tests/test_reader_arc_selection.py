"""
The reader keeps the arc it was asked for when a comic is on several lists.

A comic on two reading lists has two ``arcs`` keys, ``(3,)`` and ``(7,)``.
Opened from list 3 it must read list 3: its prev/next, its count and its
reader settings. With no usable request it falls back to the first list in
the dict's order (sort name, then pk), never to a set's hash order.
"""

from types import MappingProxyType

import pytest

from codex.collection import READER_REPRINT_COLLECTION, Collection
from codex.views.const import STORY_ARC_COLLECTION
from codex.views.reader.arcs import ReaderArcsView

_LIST_A = (3,)
_LIST_B = (7,)
_LIST_C = (11,)


def _select(arcs: dict, collection: str, ids: tuple[int, ...]) -> tuple:
    view = ReaderArcsView()
    view.params = MappingProxyType({"arc": {"collection": collection, "ids": ids}})
    view._set_selected_arc(arcs)  # noqa: SLF001
    return view._selected_arc_collection, view._selected_arc_ids  # noqa: SLF001


def _lists(*keys: tuple[int, ...]) -> dict:
    return {
        STORY_ARC_COLLECTION: {
            key: {"name": f"List {key[0]}", "mtime": None} for key in keys
        }
    }


@pytest.mark.parametrize("requested", [_LIST_A, _LIST_B, _LIST_C])
def test_requested_list_is_honoured(requested: tuple[int, ...]) -> None:
    """Each of a comic's lists, when asked for, is the one read."""
    arcs = _lists(_LIST_A, _LIST_B, _LIST_C)
    assert _select(arcs, STORY_ARC_COLLECTION, requested) == (
        STORY_ARC_COLLECTION,
        requested,
    )


@pytest.mark.parametrize(
    "order",
    [
        (_LIST_A, _LIST_B, _LIST_C),
        (_LIST_C, _LIST_B, _LIST_A),
        (_LIST_B, _LIST_C, _LIST_A),
    ],
)
def test_unknown_list_falls_back_to_the_first_in_order(
    order: tuple[tuple[int, ...], ...],
) -> None:
    """A list the comic is not on falls back to the first list in order."""
    arcs = _lists(*order)
    assert _select(arcs, STORY_ARC_COLLECTION, (99,)) == (
        STORY_ARC_COLLECTION,
        order[0],
    )


def test_missing_collection_falls_back_to_the_first_list() -> None:
    """A comic with only lists, opened from series, reads its first list."""
    arcs = _lists(_LIST_C, _LIST_A)
    assert _select(arcs, Collection.SERIES, (1,)) == (STORY_ARC_COLLECTION, _LIST_C)


def test_reprint_subset_still_matches_its_group() -> None:
    """A stale subset of a reprint group still selects that group."""
    group_a = (1, 2, 3)
    group_b = (4, 5)
    arcs = {
        READER_REPRINT_COLLECTION: {
            group_a: {"name": "A", "mtime": None},
            group_b: {"name": "B", "mtime": None},
        }
    }
    assert _select(arcs, READER_REPRINT_COLLECTION, (4,)) == (
        READER_REPRINT_COLLECTION,
        group_b,
    )

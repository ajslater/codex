"""Tests for the dual-dialect route serializer output."""

from typing import Final

from codex.serializers.route import RouteSerializer
from codex.views.util import Route

_PAGE: Final = 2


def test_emits_legacy_and_collection_dialects():
    """A parented route serializes with both group/pks and collection/parentIds."""
    data = RouteSerializer(Route("s", (5, 7), _PAGE, "X")).data
    # legacy dialect, unchanged
    assert data["group"] == "s"
    assert data["pks"] == "5,7"
    assert data["page"] == _PAGE
    # v4 dialect, additive (snake_case here; camelized at the renderer)
    assert data["collection"] == "series"
    assert data["parent_ids"] == [5, 7]


def test_root_maps_to_publishers_with_no_parent_ids():
    """The synthetic root group serializes to the publishers collection."""
    data = RouteSerializer(Route("r", (), 1, "")).data
    assert data["group"] == "r"
    assert data["pks"] == "0"
    assert data["collection"] == "publishers"
    assert data["parent_ids"] == []

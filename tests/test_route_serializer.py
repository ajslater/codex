"""Tests for the collapsed, collection-only route serializer."""

from typing import Final

from codex.serializers.route import RouteSerializer
from codex.views.util import Route

_PAGE: Final = 2
_PARENT_IDS: Final = [5, 7]


def test_emits_collection_dialect_only():
    """A parented route serializes to collection/parentIds — no legacy group/pks."""
    data = RouteSerializer(Route("series", (5, 7), _PAGE, "X")).data
    assert data["collection"] == "series"
    assert data["parent_ids"] == _PARENT_IDS
    assert data["page"] == _PAGE
    assert data["name"] == "X"
    # The redundant legacy dialect is gone.
    assert "group" not in data
    assert "pks" not in data


def test_root_maps_to_publishers_with_no_parent_ids():
    """The synthetic root group serializes to the publishers collection."""
    data = RouteSerializer(Route("root", (), 1, "")).data
    assert data["collection"] == "publishers"
    assert data["parent_ids"] == []
    assert "group" not in data
    assert "pks" not in data


def test_accepts_engine_group_pks_input():
    """Input still speaks the engine group/pks dialect (collection-valued)."""
    serializer = RouteSerializer(data={"group": "series", "pks": "5,7", "page": _PAGE})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["group"] == "series"
    assert serializer.validated_data["pks"] == (5, 7)

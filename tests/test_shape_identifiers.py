"""
Unit tests for ``shape_identifiers``.

Regression guard: the tag editor's Source ``<v-select>`` binds to the raw
source name (e.g. ``"comicvine"``), which must travel in the shaped metadata
payload. When ``shape_identifiers`` emitted only ``displayName`` the edit
screen rendered one blank row per identifier — it knew the count but could
not repopulate any field.
"""

from types import SimpleNamespace
from typing import Final

from codex.serializers.browser.metadata import (
    _SOURCE_DISPLAY_MAP,  # pyright: ignore[reportPrivateUsage]
    shape_identifiers,
)

_KNOWN_SOURCE: Final = "comicvine"


def _identifier(pk, source_name, id_type, key, url=""):
    """Fake a prefetched ``Identifier`` row with its ``source`` FK preloaded."""
    source = SimpleNamespace(name=source_name) if source_name is not None else None
    return SimpleNamespace(pk=pk, source=source, id_type=id_type, key=key, url=url)


def test_shape_identifiers_includes_raw_source():
    """Every editor field (source/type/code) is populated from one row."""
    rows = shape_identifiers([_identifier(1, _KNOWN_SOURCE, "comic", "12345")])

    assert len(rows) == 1
    row = rows[0]
    assert row["pk"] == 1
    assert row["source"] == _KNOWN_SOURCE
    assert row["type"] == "comic"
    assert row["code"] == "12345"
    # displayName stays the human label, derived from the source map.
    assert row["displayName"] == _SOURCE_DISPLAY_MAP.get(_KNOWN_SOURCE, _KNOWN_SOURCE)


def test_shape_identifiers_all_rows_have_editable_fields():
    """Four identifiers shape into four fully-populated rows, none blank."""
    identifiers = [
        _identifier(1, "comicvine", "comic", "111"),
        _identifier(2, "metron", "series", "222"),
        _identifier(3, "grandcomicsdatabase", "publisher", "333"),
        _identifier(4, "marvel", "character", "444"),
    ]
    rows = shape_identifiers(identifiers)

    assert len(rows) == len(identifiers)
    for row in rows:
        assert row["source"], "raw source must be present for the edit form"
        assert row["type"]
        assert row["code"]


def test_shape_identifiers_null_source_degrades_to_empty():
    """A null source FK yields empty strings rather than raising."""
    rows = shape_identifiers([_identifier(1, None, "comic", "12345")])

    assert rows[0]["source"] == ""
    assert rows[0]["displayName"] == ""
    assert rows[0]["code"] == "12345"


def test_shape_identifiers_empty_input():
    """``None`` and ``[]`` both shape to an empty list."""
    assert shape_identifiers(None) == []
    assert shape_identifiers([]) == []

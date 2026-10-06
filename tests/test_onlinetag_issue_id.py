"""Unit tests for parsing the numeric issue id out of a stored identifier key."""

import pytest

from codex.librarian.onlinetag.issue_id import parse_issue_id


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("12345", 12345),  # bare Metron key
        ("4000-67890", 67890),  # Comic Vine long-form -> id_key
        (67890, 67890),  # non-str key coerces
        ("https://comicvine.gamespot.com/x/4000-67890/", 67890),  # CV rule anywhere
        ("", None),
        (None, None),
        ("abc", None),  # no digits at all
        ("metron", None),
        ("4000-", None),  # long-form type without a key
        ("12-99", None),  # not the 4-digit CV rule -> not a lossy trailing int
    ],
)
def test_parse_issue_id(key, expected) -> None:
    """The CV long-key rule wins; bare digits pass; everything else is None."""
    assert parse_issue_id(key) == expected

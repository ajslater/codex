"""``parse_issue_parts`` splits issues as comicbox reads them."""

from decimal import Decimal

import pytest

from codex.models.util import parse_issue_parts


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10a", (Decimal(10), "a")),
        ("001", (Decimal(1), "")),
        ("½", (Decimal("0.5"), "")),
        ("annual", (None, "annual")),
        # comicbox 5.7 reads issue -1 as the number -1, not a suffix, so a
        # typed "#-1" has to find the column the importer wrote.
        ("-1", (Decimal(-1), "")),
        ("-1AU", (Decimal(-1), "AU")),
        ("-AU", (None, "-AU")),
        ("", (None, "")),
    ],
)
def test_parse_issue_parts(value, expected):
    """Number and suffix come apart the way comicbox splits them."""
    assert parse_issue_parts(value) == expected

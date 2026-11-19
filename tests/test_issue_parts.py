"""
Splitting a compound issue string into number and suffix.

comicbox 5.6.2 reads issue ``-1`` as the number -1 with an empty suffix;
5.6.1 read it as no number and the suffix ``-1``. ``parse_issue_parts``
splits ``Reprint`` issues and ``issue:`` searches, so it must agree with
the importer or an ``issue:-1`` search misses every imported -1 issue.
"""

from decimal import Decimal

import pytest
from django.db.models import CharField

from codex.models.util import parse_issue_parts
from codex.views.browser.filters.search.field.expression import parse_expression


@pytest.mark.parametrize(
    ("issue", "expected"),
    [
        ("-1", (Decimal(-1), "")),
        ("-1AU", (Decimal(-1), "AU")),
        ("-AU", (None, "-AU")),
        ("-.5", (Decimal("-0.5"), "")),
        ("10a", (Decimal(10), "a")),
        ("1½", (Decimal("1.5"), "")),
        ("annual", (None, "annual")),
        ("", (None, "")),
    ],
)
def test_parse_issue_parts(issue: str, expected: tuple) -> None:
    """A leading minus belongs to the number only when a digit follows."""
    assert parse_issue_parts(issue) == expected


def test_issue_search_minus_one() -> None:
    """``issue:-1`` searches the number -1 with an empty suffix."""
    assert parse_expression("issue", CharField, "-1") == {
        "issue_number": Decimal(-1),
        "issue_suffix": "",
    }

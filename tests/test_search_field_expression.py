"""
Size suffixes and two-character operators in field search expressions.

Both lookup tables were matched in insertion order by the first prefix
or suffix hit. ``b`` came before ``kb``, so ``10kb`` parsed as ``10k``
bytes and raised; ``>`` came before ``>=``, so ``>=5`` parsed as ``>``
with the value ``=5``. The search filter swallows the error and silently
drops the term.
"""

import pytest

from codex.views.browser.filters.search.field.column import parse_field
from codex.views.browser.filters.search.field.expression import (
    parse_expression,
    parse_size,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("7", 7),
        ("10b", 10),
        ("10kb", 10 * 1024),
        ("1.5mb", int(1.5 * 1024**2)),
        ("2gb", 2 * 1024**3),
        ("3 TB", 3 * 1024**4),
    ],
)
def test_parse_size(text: str, expected: int) -> None:
    """Every unit suffix parses, not just bare bytes."""
    assert parse_size(text) == expected


@pytest.mark.parametrize(
    ("exp", "expected"),
    [
        (">=10kb", {"size__gte": 10 * 1024}),
        ("<=5", {"size__lte": 5}),
        (">5", {"size__gt": 5}),
        ("<5", {"size__lt": 5}),
    ],
)
def test_parse_expression_operators(exp: str, expected: dict) -> None:
    """Each comparison operator maps to its own lookup."""
    rel_class, rel, _ = parse_field("size")
    assert parse_expression(rel, rel_class, exp) == expected

"""Utilities for models."""

import re
from decimal import Decimal, InvalidOperation

from comicbox.formats.base.fields.fields import IssueField

# Splits a normalized issue string into its numeric head and the
# remaining suffix ("10a" -> "10" + "a"). Shared by every compound
# issue column (``Comic.issue_number``/``issue_suffix``,
# ``Reprint.issue_number``/``issue_suffix``) and by the search
# field parser so a typed query and a stored column agree.
_PARSE_ISSUE_MATCHER = re.compile(r"(?P<issue_number>\d*\.?\d*)(?P<issue_suffix>.*)")

# Multi-language leading-article set used by ``get_sort_name`` to
# move a leading "the"/"el"/"der"/etc. to the end so titles sort by
# the first significant word. Comments mark which language each
# group came from; cross-language collisions (English "as" vs
# Portuguese "as", English "i" vs Italian "i", etc.) are
# intentionally absent.
_ARTICLES = frozenset(
    {
        # en
        "a", "an", "the",
        # es
        "un", "unos", "unas", "el", "los", "la", "las",
        # fr (l' is shared with it)
        "une", "le", "les", "l'",
        # pt
        "o", "os",
        # de (den & die conflict with English)
        "der", "dem", "des", "das",
        # it (i conflicts with English)
        "il", "lo", "gli",
        # nl
        "de", "het", "een",
        # sw / no / da
        "en", "ett", "ei", "et",
        # ct
        "els", "una", "uns", "unes", "na",
    }
)  # fmt: skip


def parse_issue_parts(value) -> tuple[Decimal | None, str]:
    """Split a compound issue string into its number and suffix parts."""
    value = IssueField.parse_issue(value)
    if not value:
        return None, ""
    matches = _PARSE_ISSUE_MATCHER.match(value)
    if not matches:
        return None, ""
    try:
        number = Decimal(matches.group("issue_number"))
    except InvalidOperation:
        # A suffix-only issue ("annual", "½") leaves the numeric group
        # empty, which Decimal rejects. Keep the suffix; sort it as null.
        number = None
    return number, matches.group("issue_suffix")


def get_sort_name(name: str) -> str:
    """Create sort_name from name."""
    lower_name = name.lower()
    name_parts = lower_name.split()
    if len(name_parts) > 1 and (first_word := name_parts[0]) in _ARTICLES:
        return " ".join(name_parts[1:]) + ", " + first_word
    return lower_name

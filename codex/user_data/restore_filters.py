"""
Read the filters settings that are not lists of pks from a backup.

Split out of :mod:`codex.user_data.restore`: the Reading List Kind and the
filters set to match all ticked values. Each drops what it does not know,
so an older or a development backup restores to something valid.
"""

from __future__ import annotations

import json

from codex.choices.browser import (
    BROWSER_MATCH_ALL_FILTERS,
    BROWSER_READING_LIST_KIND_CHOICES,
)


def restore_list_kinds(row_keys, row) -> list[str]:
    """
    Read the Reading List Kind: a list, or a development build's one value.

    A development build stored one bare kind, or ``""`` for every list.
    Unknown kinds drop.
    """
    raw = row["reading_list_kind"] if "reading_list_kind" in row_keys else ""
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        value = raw
    if isinstance(value, str):
        return [value] if value in BROWSER_READING_LIST_KIND_CHOICES else []
    if not isinstance(value, list):
        return []
    return [
        kind
        for kind in dict.fromkeys(value)
        if isinstance(kind, str) and kind in BROWSER_READING_LIST_KIND_CHOICES
    ]


def restore_match_all(row_keys, row) -> list[str]:
    """Read the filters set to All; a name that is no tag-like filter drops."""
    raw = row["match_all"] if "match_all" in row_keys else ""
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [
        name
        for name in dict.fromkeys(value)
        if isinstance(name, str) and name in BROWSER_MATCH_ALL_FILTERS
    ]

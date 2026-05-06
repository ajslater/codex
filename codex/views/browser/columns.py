"""
Helpers around the browser table-view column registry.

The registry itself lives in :mod:`codex.choices.browser` so the choices
JSON build pipeline can pick it up. This module provides the runtime
helpers used by the views, serializers, and validators.
"""

from typing import cast

from codex.choices.browser import (
    BROWSER_TABLE_COLUMNS,
    BROWSER_TABLE_DEFAULT_COLUMNS,
)


def default_columns_for(top_group: str) -> tuple[str, ...]:
    """Return the default column tuple for a top-group, or empty if unknown."""
    return BROWSER_TABLE_DEFAULT_COLUMNS.get(top_group, ())


def is_sortable(column_key: str) -> bool:
    """Return True when clicking the column header should drive ``order_by``."""
    entry = BROWSER_TABLE_COLUMNS.get(column_key)
    return bool(entry and entry["sort_key"])


def is_m2m(column_key: str) -> bool:
    """Return True when the column's value comes from a Many-to-Many relation."""
    entry = BROWSER_TABLE_COLUMNS.get(column_key)
    return bool(entry and entry["m2m"])


def sort_key_for(column_key: str) -> str | None:
    """Return the ``order_by`` enum key the column maps to, or None."""
    entry = BROWSER_TABLE_COLUMNS.get(column_key)
    if entry is None:
        return None
    # Registry values are heterogeneous (str | bool | None); narrow here.
    return cast("str | None", entry["sort_key"])

"""
Helpers around the browser table-view column registry.

The registry itself lives in :mod:`codex.choices.browser` so the choices
JSON build pipeline can pick it up. This module provides the runtime
helpers used by the views, serializers, and validators.
"""

from types import MappingProxyType
from typing import cast

from django.db.models import Aggregate

from codex.choices.browser import (
    BROWSER_TABLE_COLUMNS,
    BROWSER_TABLE_DEFAULT_COLUMNS,
)
from codex.models.functions import JsonGroupArray

# ORM paths for the M2M columns whose value is the related model's
# ``name`` field. Columns whose aggregation requires a more elaborate
# traversal (``credits`` -> person/role, ``identifiers`` -> source/key,
# ``story_arcs`` -> through-model) are deferred to a follow-up; they
# stay null until that lands.
_M2M_COLUMN_PATHS = MappingProxyType(
    {
        "characters": "characters__name",
        "genres": "genres__name",
        "locations": "locations__name",
        "series_groups": "series_groups__name",
        "stories": "stories__name",
        "tags": "tags__name",
        "teams": "teams__name",
        "universes": "universes__name",
    }
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


# Annotation aliases must not collide with Comic field names
# (``Comic.genres``, ``Comic.tags``, etc. are existing ManyToManyField
# attributes, so ``qs.annotate(genres=...)`` raises). Prefix the
# annotation alias and have :func:`m2m_alias_for` provide the
# round-trip; ``_row_repr`` reads via this alias.
_M2M_ANNOTATION_PREFIX = "_table_m2m_"


def m2m_alias_for(column_key: str) -> str:
    """Return the queryset annotation alias for an M2M column key."""
    return _M2M_ANNOTATION_PREFIX + column_key


def m2m_annotations_for(columns: tuple[str, ...]) -> dict[str, Aggregate]:
    """
    Build a dict of ``alias -> JsonGroupArray`` for requested M2M columns.

    Only columns whose ORM path is known (see ``_M2M_COLUMN_PATHS``)
    contribute an annotation. Other M2M columns are deferred and stay
    null in the response. The empty dict is meaningful: it tells the
    caller "skip the M2M annotation step entirely".
    """
    annotations: dict[str, Aggregate] = {}
    for col in columns:
        path = _M2M_COLUMN_PATHS.get(col)
        if path is not None:
            annotations[m2m_alias_for(col)] = JsonGroupArray(path, distinct=True)
    return annotations


def m2m_columns() -> frozenset[str]:
    """Return the set of M2M column keys whose annotation is wired."""
    return frozenset(_M2M_COLUMN_PATHS.keys())

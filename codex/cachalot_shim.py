"""
Let cachalot see the subqueries of codex's ``GroupByQuery``.

cachalot reads the tables of a ``WHERE x__in=<subquery>`` through
``cachalot.utils._find_rhs_lhs_subquery``, which tests the subquery's class
by identity: ``is Query``, ``is QuerySet``. Every codex model's manager is a
``GroupByManager`` whose queries are ``GroupByQuery(Query)``, so the
subquery's table was skipped: the query was cached with no dependency on it
and served stale after a write to it (the reading lists browser filter, for
one).

``CACHALOT_FINAL_SQL_CHECK`` catches these too, but measured +27% on the
median warm browse request. Replacing this one function with an
``isinstance`` version costs nothing.

It does not reach a subquery nested in ``When(pk__in=...)`` or an aggregate's
``filter=``; those queries still need ``cachalot_disabled()`` or an
``Exists``.
"""

from typing import Any, Final

from cachalot import utils
from django.db.models import Exists, QuerySet, Subquery
from django.db.models.sql.query import Query

# The one cachalot function replaced; ``_find_subqueries_in_where`` looks it
# up by this module-global name on every call.
_PATCHED_NAME: Final = "_find_rhs_lhs_subquery"


def _find_rhs_lhs_subquery(side: Any) -> Query | None:
    """Return the subquery a WHERE side holds, for subclasses too."""
    if isinstance(side, Query):
        return side
    if isinstance(side, QuerySet):
        return side.query
    if isinstance(side, Subquery | Exists):
        # Set in Subquery.__init__; the stubs do not declare it.
        inner = vars(side)["query"]
        return inner.query if isinstance(inner, QuerySet) else inner
    if side.__class__ in utils.UNCACHABLE_FUNCS:
        raise utils.UncachableQuery
    return None


def install_cachalot_shim() -> None:
    """Replace cachalot's identity-tested subquery finder."""
    setattr(utils, _PATCHED_NAME, _find_rhs_lhs_subquery)

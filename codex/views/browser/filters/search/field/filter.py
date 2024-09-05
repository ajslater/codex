"""Parse the browser query by removing field queries and doing them with the ORM."""

from django.db.models import Q

from codex.logger.logging import get_logger
from codex.views.browser.filters.field import ComicFieldFilterView
from codex.views.browser.filters.search.field.column import parse_field
from codex.views.browser.filters.search.field.parse import get_field_query

LOG = get_logger(__name__)


class BrowserFieldQueryFilter(ComicFieldFilterView):
    """Parse the browser query by removing field queries and doing them with the ORM."""

    @staticmethod
    def _combine_q(q, other_q, op):
        if isinstance(other_q, tuple):
            other_q = Q(**{other_q[0]: other_q[1]})
        if op == Q.AND:
            q &= other_q
        else:
            q |= other_q
        return q

    @classmethod
    def _hoist_not_filters_for_exclude(cls, filter_q, exclude_q, new_q):
        """Turn not queries for m2m queries into excludes."""
        if new_q.connector == Q.AND:
            for child in new_q.children:
                if isinstance(child, Q) and child.negated:
                    child.negated = False
                    exclude_q = cls._combine_q(exclude_q, child, new_q.connector)
                else:
                    filter_q = cls._combine_q(filter_q, child, new_q.connector)
        else:
            filter_q = cls._combine_q(filter_q, new_q, new_q.connector)
        return filter_q, exclude_q

    def _parse_field_query(self, col, exp, model, filter_q, exclude_q):
        try:
            rel_class, rel, many_to_many = parse_field(col)

            q = get_field_query(rel, rel_class, exp, model, many_to_many)
            if q and many_to_many:
                filter_q, exclude_q = self._hoist_not_filters_for_exclude(
                    filter_q, exclude_q, q
                )
            else:
                filter_q &= q
        except Exception as exc:
            token = f"{col}:{exp}"
            msg = f"Parsing field query {token} - {exc}"
            LOG.warning(msg)
            self.search_error = msg
        return filter_q, exclude_q

    def get_search_field_filters(self, model, field_token_pairs):
        """Parse and apply field query filters."""
        filter_q = Q()
        exclude_q = Q()
        for col, exp in field_token_pairs:
            filter_q, exclude_q = self._parse_field_query(
                col, exp, model, filter_q, exclude_q
            )

        return filter_q, exclude_q

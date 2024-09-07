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
            rel, val = other_q
            if rel.endswith("__like") and val == "%":
                # Remove likes that would match everything
                return q
            other_q = Q(**{rel: val})
        if op == Q.AND:
            q &= other_q
        else:
            q |= other_q
        return q

    @classmethod
    def _hoist_filters(cls, filter_q_list, exclude_q_list, new_q):
        """Peel top layer of queries into multiple filter and exclude clauses."""
        # This makes m2m queries behave more as expected and may optimize fk queries.
        if new_q.connector == Q.AND:
            for child in new_q.children:
                if isinstance(child, Q) and child.negated:
                    child.negated = False
                    q = cls._combine_q(Q(), child, new_q.connector)
                    exclude_q_list.append(q)
                else:
                    q = cls._combine_q(Q(), child, new_q.connector)
                    filter_q_list.append(q)
        else:
            filter_q_list[0] = cls._combine_q(filter_q_list[0], new_q, new_q.connector)

    def _parse_field_query(self, col, exp, model, filter_q_list, exclude_q_list):
        try:
            rel_class, rel, many_to_many = parse_field(col)

            if q := get_field_query(rel, rel_class, exp, model, many_to_many):
                self._hoist_filters(filter_q_list, exclude_q_list, q)
        except Exception as exc:
            token = f"{col}:{exp}"
            msg = f"Parsing field query {token} - {exc}"
            LOG.warning(msg)
            self.search_error = msg

    def get_search_field_filters(self, model, field_token_pairs):
        """Parse and apply field query filters."""
        filter_q_list = []
        exclude_q_list = []
        if not field_token_pairs:
            return filter_q_list, exclude_q_list

        filter_q_list.append(Q())
        exclude_q_list.append(Q())
        for col, exp in field_token_pairs:
            self._parse_field_query(col, exp, model, filter_q_list, exclude_q_list)

        return filter_q_list, exclude_q_list

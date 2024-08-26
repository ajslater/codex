"""Parse the browser query by removing field queries and doing them with the ORM."""

from django.db.models import Q

from codex.logger.logging import get_logger
from codex.views.browser.filters.field import ComicFieldFilterView
from codex.views.browser.filters.search.field.column import parse_field
from codex.views.browser.filters.search.field.parse import gen_query

LOG = get_logger(__name__)


class BrowserFieldQueryFilter(ComicFieldFilterView):
    """Parse the browser query by removing field queries and doing them with the ORM."""

    def _parse_field_query(self, col, exp, model):
        """Parse one field query."""
        rel_class, rel, many_to_many = parse_field(col)
        if not rel_class or not rel:
            LOG.debug(f"Unknown field specified in search query {col}")
            return None

        return gen_query(rel, rel_class, exp, model, many_to_many)

    @staticmethod
    def _hoist_not_filters_for_exclude(filters, excludes, q):
        """Fix not filters for m2m queries. Also optimizes for other queries."""
        if q.connector == Q.AND:
            for child in q.children:
                if isinstance(child, Q) and child.negated:
                    excludes.append(~child)
                else:
                    filters.append(child)
        else:
            filters.append(q)

    def apply_field_query_filters(self, qs, model, field_token_pairs):
        """Parse and apply field query filters."""
        filters = []
        excludes = []
        for col, exp in field_token_pairs:
            try:
                if q := self._parse_field_query(col, exp, model):
                    self._hoist_not_filters_for_exclude(filters, excludes, q)
            except Exception:
                LOG.exception(f"Parsing field query {col}:{exp}")
        if filters:
            qs = qs.filter(*filters)
        if excludes:
            qs = qs.exclude(*excludes)
        return qs

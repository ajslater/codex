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
    def _hoist_not_filters_for_exclude(filters, excludes, q):
        """Fix not filters for m2m queries. Also optimizes for other queries."""
        if not q:
            return
        if q.connector == Q.AND:
            for child in q.children:
                if isinstance(child, Q) and child.negated:
                    excludes.append(~child)
                else:
                    filters.append(child)
        else:
            filters.append(q)

    def _parse_field_query(self, col, exp, model, filters, excludes):
        try:
            rel_class, rel, many_to_many = parse_field(col)
            if not rel_class or not rel:
                LOG.debug(f"Unknown field specified in search query {col}")
                return

            q = get_field_query(rel, rel_class, exp, model, many_to_many)
            self._hoist_not_filters_for_exclude(filters, excludes, q)
        except Exception as exc:
            LOG.warning(f"Parsing field query {col}:{exp} - {exc}")
            self.search_error = True

    def get_search_field_filters(self, model, field_token_pairs):
        """Parse and apply field query filters."""
        filters = []
        excludes = []
        for col, exp in field_token_pairs:
            self._parse_field_query(col, exp, model, filters, excludes)
        return filters, excludes

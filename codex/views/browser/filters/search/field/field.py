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

    def apply_field_query_filters(self, qs, model, field_token_pairs):
        """Parse and apply field query filters."""
        q = Q()
        for col, exp in field_token_pairs:
            try:
                if q_part := self._parse_field_query(col, exp, model):
                    q &= q_part
            except Exception:
                LOG.exception(f"Parsing field query {col}:{exp}")
        # print(q)
        if q:
            qs = qs.filter(q)
        return qs

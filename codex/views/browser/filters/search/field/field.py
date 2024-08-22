"""Parse the browser query by removing field queries and doing them with the ORM."""

from django.db.models import Q

from codex.logger.logging import get_logger
from codex.models.comic import Comic
from codex.views.browser.filters.field import ComicFieldFilterView
from codex.views.browser.filters.search.field.column import parse_field
from codex.views.browser.filters.search.field.parse import gen_query

LOG = get_logger(__name__)


class BrowserFieldQueryFilter(ComicFieldFilterView):
    """Parse the browser query by removing field queries and doing them with the ORM."""

    @staticmethod
    def _add_query_dict_to_query(query_dict, or_operator, model):
        """Convert the query dict into django orm queries."""
        prefix = "" if model == Comic else "comic__"  # type: ignore
        model_span = model.__name__.lower() + "__"
        query = None
        for key, data_set in query_dict.items():
            rel = (
                key.removeprefix(model_span)
                if key.startswith(model_span)
                else prefix + key
            )
            for data in data_set:
                value, query_not = data
                prefixed_query_dict = {rel: value}
                query_part = (
                    ~Q(**prefixed_query_dict) if query_not else Q(**prefixed_query_dict)
                )
                if not query:
                    query = Q()
                if or_operator:
                    query |= query_part
                else:
                    query &= query_part
        return query

    def _parse_expression(self, rel, rel_class, exp, model):
        # TODO replace with the pyparser parser
        # remove query dict and return the Q
        # OLD
        # ManyToMany char fields are forced into OR operation because AND
        # is too difficult with regex & contains
        # TODO change to rel_class in (CharField, ForeignKeyField, ManyToManyField)
        # Don't use many_to_many?
        # or_operator = many_to_many and rel_class == CharField
        # or_operator = rel_class == CharField

        return gen_query(rel, rel_class, exp, model)

    def _parse_field_query(self, col, exp, model, qs):
        """Parse one field query."""
        rel_class, rel, _many_to_many = parse_field(col)
        if not rel_class or not rel:
            LOG.debug(f"Unknown field specified in search query {col}")
            return qs, None

        # optimized_dict, or_operator = self._parse_expression(rel, rel_class, exp, model)
        q = self._parse_expression(rel, rel_class, exp, model)

        return qs, q
        # self._add_query_dict_to_query(optimized_dict, or_operator, model)

    def apply_field_query_filters(self, qs, model, field_token_pairs):
        """Parse and apply field query filters."""
        field_query = Q()
        for col, exp in field_token_pairs:
            try:
                qs, field_query_part = self._parse_field_query(col, exp, model, qs)
                if field_query_part:
                    field_query &= field_query_part
            except Exception:
                LOG.exception(f"Parsing field query {col}:{exp}")
        if field_query:
            qs = qs.filter(field_query)
        return qs

"""Parse the browser query by removing field queries and doing them with the ORM."""

from typing import Any

from django.db.models import Q
from loguru import logger

from codex.models.base import BaseModel
from codex.views.browser.filters.field import ComicFieldFilterView
from codex.views.browser.filters.search.field.column import parse_field
from codex.views.browser.filters.search.field.parse import get_field_query


class BrowserFieldQueryFilter(ComicFieldFilterView):
    """Parse the browser query by removing field queries and doing them with the ORM."""

    @staticmethod
    def _combine_q(q: Q, other_q: tuple[str, Any] | Q, op: str) -> Q:
        if isinstance(other_q, tuple):
            rel: str
            rel, val = other_q  # ty: ignore[invalid-assignment]
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
    def _hoist_filters(
        cls, filter_q_list: list[Q], exclude_q_list: list[Q], new_q: Q
    ) -> None:
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

    def _parse_field_query(
        self,
        col: str,
        exp: str,
        model: type[BaseModel],
        filter_q_list: list[Q],
        exclude_q_list: list[Q],
    ) -> None:
        try:
            rel_class, rel, many_to_many = parse_field(col)

            if q := get_field_query(
                rel, rel_class, exp, model, many_to_many=many_to_many
            ):
                self._hoist_filters(filter_q_list, exclude_q_list, q)
        except Exception as exc:
            token = f"{col}:{exp}"
            msg = f"Parsing field query {token} - {exc}"
            logger.warning(msg)
            self.search_error = msg

    def _parse_compound_field_query(
        self,
        cols: tuple[str, ...],
        exp: str,
        model: type[BaseModel],
        filter_q_list: list[Q],
        exclude_q_list: list[Q],
    ) -> None:
        """Parse a compound alias (e.g. protagonist) into an OR'd Q across columns."""
        compound_q = Q()
        for col in cols:
            try:
                rel_class, rel, many_to_many = parse_field(col)
                if q := get_field_query(
                    rel, rel_class, exp, model, many_to_many=many_to_many
                ):
                    compound_q |= q
            except Exception as exc:
                token = f"{col}:{exp}"
                msg = f"Parsing compound field query {token} - {exc}"
                logger.warning(msg)
                self.search_error = msg
        if compound_q:
            self._hoist_filters(filter_q_list, exclude_q_list, compound_q)

    def get_search_field_filters(self, model, field_token_pairs) -> tuple[list, list]:
        """Parse and apply field query filters."""
        filter_q_list = []
        exclude_q_list = []
        if not field_token_pairs:
            return filter_q_list, exclude_q_list

        filter_q_list.append(Q())
        exclude_q_list.append(Q())
        for col, exp in field_token_pairs:
            if isinstance(col, tuple):
                self._parse_compound_field_query(
                    col, exp, model, filter_q_list, exclude_q_list
                )
            else:
                self._parse_field_query(col, exp, model, filter_q_list, exclude_q_list)

        return filter_q_list, exclude_q_list

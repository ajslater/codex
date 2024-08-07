"""Parse the browser query by removing field queries and doing them with the ORM."""

import shlex
from decimal import Decimal
from types import MappingProxyType

from dateutil import parser
from django.db.models import (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    Q,
    TextField,
)
from django.db.models.fields import DecimalField, PositiveSmallIntegerField
from django.db.models.fields.related import ForeignKey, ManyToManyField
from humanfriendly import parse_size

from codex.logger.logging import get_logger
from codex.models.comic import Comic
from codex.search.fields import FIELDMAP
from codex.views.browser.filters.field import ComicFieldFilterView
from codex.views.const import FALSY

_ALIAS_FIELD_MAP = MappingProxyType(
    {
        value: "path" if key == "search_path" else key
        for key, values in FIELDMAP.items()
        for value in values
    }
)
_FIELD_TYPE_MAP = MappingProxyType(
    {
        **{field.name: field.__class__ for field in Comic._meta.get_fields()},
        "role": ManyToManyField,
    }
)
_EXCLUDE_FIELD_NAMES = frozenset({"stat", "parent_folder", "library"})

LOG = get_logger(__name__)


class BrowserQueryParser(ComicFieldFilterView):
    """Parse the browser query by removing field queries and doing them with the ORM."""

    @staticmethod
    def _parse_operator(token, operator, field, value):
        field += "__" + operator
        value = value[len(token) :]
        return field, value

    @staticmethod
    def _cast_value(field_class, value):
        if field_class == PositiveSmallIntegerField:
            value = int(value)
        elif field_class == DecimalField:
            value = Decimal(value)
        elif field_class == BooleanField:
            value = value not in FALSY
        elif field_class in (DateTimeField, DateField):
            value = parser.parse(value)
        return value

    @classmethod
    def _parse_range_filter(cls, token, field, field_class, value, query_dict):
        range_from_value, range_to_value = value.split(token)
        query_dict[field + "__gte"] = cls._cast_value(field_class, range_from_value)
        query_dict[field + "__lte"] = cls._cast_value(field_class, range_to_value)

    def _parse_field(self, field_name, model):
        if field_name in _EXCLUDE_FIELD_NAMES:
            return None, None
        if field_name == "path" and not (
            self.admin_flags["folder_view"] or self.is_admin()  # type: ignore
        ):
            return None, None
        field_name = _ALIAS_FIELD_MAP.get(field_name, field_name)
        field_class = _FIELD_TYPE_MAP.get(field_name)
        if not field_class:
            return None, None

        # TODO
        # full issue number

        if field_name == "role":
            field = "contributors__role__name"
        elif field_class in (ForeignKey, ManyToManyField):
            field = field_name + "__name"
        elif field_name == "contributors":
            field = "contributors__person__name"
        elif field_name == "identifier":
            field = "identifier__nss"
        elif field_name == "identifier_type":
            field = "identifier__identifier_type__name"
        elif field_name == "story_arcs":
            field = "story_arc_number__story_arc__name"
        else:
            field = field_name

        prefix = "" if model == Comic else "comic__"  # type: ignore
        return field_class, prefix + field

    def _parse_value(self, field, field_class, value_part, query_dict):
        query_not = False
        if value_part.startswith("!"):
            operator = "__icontains" if field_class in (CharField, TextField) else ""
            field, value_str = self._parse_operator("!", operator, field, value_part)
            query_not = True
        if value_part.startswith(">="):
            field, value_str = self._parse_operator(">=", "gte", field, value_part)
        elif value_part.startswith(">"):
            field, value_str = self._parse_operator(">", "gt", field, value_part)
        elif value_part.startswith("<="):
            field, value_str = self._parse_operator("<=", "lte", field, value_part)
        elif value_part.startswith("<"):
            field, value_str = self._parse_operator("<", "lt", field, value_part)
        elif "..." in value_part:
            self._parse_range_filter("...", field, field_class, value_part, query_dict)
            value_str = ""
        elif ".." in value_part:
            self._parse_range_filter("..", field, field_class, value_part, query_dict)
            value_str = ""
        elif field_class in (CharField, TextField):
            field += "__icontains"
            value_str = value_part
        elif field.endswith("size"):
            value_str = parse_size(value_part)
        else:
            value_str = value_part
        # TODO regex operator & ! regex operator

        parsed_value = None if query_dict else self._cast_value(field_class, value_str)
        return field, parsed_value, query_not

    def _parse_field_filter(self, field_filter, model):
        key, value = field_filter.split(":")
        field_class, field = self._parse_field(key, model)
        query = Q()
        if not field_class:
            LOG.debug(f"Unknown field specified in search query {key}")
            return query

        query_dict = {}
        for value_part in value.split(","):
            part_field, parsed_value, query_not = self._parse_value(
                field, field_class, value_part, query_dict
            )

            if not query_dict:
                query_dict[part_field] = parsed_value

            query_part = ~Q(**query_dict) if query_not else Q(**query_dict)
            query = query & query_part
        return query

    def preparse_search_query(self, qs, model):
        """Preparse search fields out of query text."""
        q = self.params.get("q")  # type: ignore
        if not q:
            return qs, q

        parts = shlex.split(q)
        search_query_parts = []
        for part in parts:
            if ":" in part:
                try:
                    filter_query = self._parse_field_filter(part, model)
                    qs = qs.filter(filter_query)
                except Exception:
                    LOG.exception("parse query field")
            elif part:
                search_query_parts.append(part)

        preparsed_search_query = shlex.join(search_query_parts).strip()
        return qs, preparsed_search_query

"""Parse the browser query by removing field queries and doing them with the ORM."""

import re
import shlex
from decimal import Decimal

from comicbox.fields.fields import IssueField
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
from codex.views.browser.filters.field import ComicFieldFilterView
from codex.views.browser.filters.search.aliases import ALIAS_FIELD_MAP, FIELD_TYPE_MAP
from codex.views.const import FALSY

_EXCLUDE_FIELD_NAMES = frozenset({"stat", "parent_folder", "library"})
_PARSE_ISSUE_MATCHER = re.compile(r"(?P<issue_number>\d*\.?\d*)(?P<issue_suffix>.*)")

LOG = get_logger(__name__)


class BrowserQueryFieldParser(ComicFieldFilterView):
    """Parse the browser query by removing field queries and doing them with the ORM."""

    @staticmethod
    def _parse_operator(token, operator, rel, value):
        """Move value operator out of value into relation operator."""
        if operator:
            rel += "__" + operator
        value = value[len(token) :]
        return rel, value

    @staticmethod
    def _cast_value(rel_class, value):
        """Cast values by relation class."""
        if rel_class == PositiveSmallIntegerField:
            value = int(value)
        elif rel_class == DecimalField:
            value = Decimal(value)
        elif rel_class == BooleanField:
            value = value not in FALSY
        elif rel_class in (DateTimeField, DateField):
            value = parser.parse(value)
        return value

    @classmethod
    def _parse_operator_range(cls, token, rel, rel_class, value, query_dict):
        """Parse range operator."""
        range_from_value, range_to_value = value.split(token)
        query_dict[rel + "__gte"] = cls._cast_value(rel_class, range_from_value)
        query_dict[rel + "__lte"] = cls._cast_value(rel_class, range_to_value)

    def _parse_field(self, field_name):
        """Parse the field size of the query in to database relations."""
        if field_name in _EXCLUDE_FIELD_NAMES:
            return None, None
        if field_name == "path" and not (
            self.admin_flags["folder_view"] or self.is_admin()  # type: ignore
        ):
            return None, None
        field_name = ALIAS_FIELD_MAP.get(field_name, field_name)
        rel_class = FIELD_TYPE_MAP.get(field_name)
        if not rel_class:
            return None, None

        # Comic relations
        if field_name == "role":
            rel = "contributors__role__name"
            rel_class = CharField
        elif field_name == "contributors":
            rel = "contributors__person__name"
            rel_class = CharField
        elif field_name == "identifier":
            rel = "identifier__nss"
            rel_class = CharField
        elif field_name == "identifier_type":
            rel = "identifier__identifier_type__name"
            rel_class = CharField
        elif field_name == "story_arcs":
            rel = "story_arc_number__story_arc__name"
            rel_class = CharField
        elif rel_class in (ForeignKey, ManyToManyField):
            # This must be next to last
            rel = field_name + "__name"
            rel_class = CharField
        else:
            # Comic attribute
            rel = field_name

        return rel_class, rel

    @staticmethod
    def _parse_operator_text(value):
        """Parse text value operators."""
        if "*" in value:
            operator = "iregex"
            value = ".*" + value.replace("*", ".*") + ".*"
        else:
            operator = "icontains"
        return operator, value

    @classmethod
    def _parse_operator_not(cls, rel_class, rel, value):
        """Parse value not operator."""
        if rel_class in (CharField, TextField):
            operator, value = cls._parse_operator_text(value)
        else:
            operator = ""
        return cls._parse_operator("!", operator, rel, value)

    @staticmethod
    def _parse_size_values(query_dict):
        """Size values can be encoded with common size suffixes."""
        for key in tuple(query_dict.keys()):
            size_value = query_dict[key]
            query_dict[key] = parse_size(size_value)

    @staticmethod
    def _parse_issue_value(value):
        """Parse a compound issue value into number & suffix."""
        value = IssueField.parse_issue(value)
        if not value:
            return None, None
        matches = _PARSE_ISSUE_MATCHER.match(value)
        if not matches:
            return None, None
        number_value = Decimal(matches.group("issue_number"))
        suffix_value = matches.group("issue_suffix")

        return number_value, suffix_value

    @classmethod
    def _parse_issue_values(cls, query_dict, query_not, is_operator_query):
        """Issue is not a column. Convert to issue_number and issue_suffix."""
        issue_query_dict = {}
        use_issue_number_only = query_not or is_operator_query
        for key in tuple(query_dict.keys()):
            value = query_dict.pop(key)
            issue_number_value, issue_suffix_value = cls._parse_issue_value(value)
            if issue_number_value is None:
                continue
            issue_number_field = key.replace("issue", "issue_number")
            issue_query_dict[issue_number_field] = issue_number_value
            if not use_issue_number_only and issue_suffix_value:
                issue_suffix_field = key.replace("issue", "issue_suffix")
                issue_query_dict[issue_suffix_field] = issue_suffix_value
        query_dict.update(issue_query_dict)

    @classmethod
    def _parse_value_operators(cls, rel, rel_class, value, query_dict):
        """Parse the operators of the value size of the field query."""
        query_not = False
        is_operator_query = True
        value = value.strip()
        if value.startswith("!"):
            rel, value_str = cls._parse_operator_not(rel_class, rel, value)
            query_not = True
        elif value.startswith(">="):
            rel, value_str = cls._parse_operator(">=", "gte", rel, value)
        elif value.startswith(">"):
            rel, value_str = cls._parse_operator(">", "gt", rel, value)
        elif value.startswith("<="):
            rel, value_str = cls._parse_operator("<=", "lte", rel, value)
        elif value.startswith("<"):
            rel, value_str = cls._parse_operator("<", "lt", rel, value)
        elif "..." in value:
            cls._parse_operator_range("...", rel, rel_class, value, query_dict)
            value_str = ""
        elif ".." in value:
            cls._parse_operator_range("..", rel, rel_class, value, query_dict)
            value_str = ""
        elif rel_class in (CharField, TextField):
            operator, value_str = cls._parse_operator_text(value)
            rel += "__" + operator
        else:
            # Exact match for non-string fields
            is_operator_query = False
            value_str = value

        return rel, value_str, query_not, is_operator_query

    @classmethod
    def _parse_value_special_fields(cls, rel, query_not, is_operator_query, query_dict):
        """Post process special values in query_dict."""
        if rel.startswith("size"):
            cls._parse_size_values(query_dict)
        elif rel.startswith("issue"):
            cls._parse_issue_values(query_dict, query_not, is_operator_query)

    @classmethod
    def _parse_value(cls, rel, rel_class, value_part, query_dict):
        """Parse the value side of the field query into the query dict."""
        rel, value_str, query_not, is_operator_query = cls._parse_value_operators(
            rel, rel_class, value_part, query_dict
        )

        if not query_dict:
            parsed_value = cls._cast_value(rel_class, value_str)
            query_dict[rel] = parsed_value

        cls._parse_value_special_fields(rel, query_not, is_operator_query, query_dict)

        return query_not

    @classmethod
    def _parse_field_query_value(cls, rel, rel_class, value, prefix):
        """Parse the value side of the field query into a query."""
        query_dict = {}
        query_not = cls._parse_value(rel, rel_class, value, query_dict)
        prefixed_query_dict = {}
        for key in tuple(query_dict.keys()):
            prefixed_key = prefix + key
            prefixed_query_dict[prefixed_key] = query_dict[key]
        return ~Q(**prefixed_query_dict) if query_not else Q(**prefixed_query_dict)

    def _parse_field_query(self, field_filter, model):
        """Parse one field query."""
        key, value = field_filter.split(":")

        rel_class, rel = self._parse_field(key)
        query = Q()
        if not rel_class:
            LOG.debug(f"Unknown field specified in search query {key}")
            return query

        prefix = "" if model == Comic else "comic__"  # type: ignore
        for value_part in value.split(","):
            query &= self._parse_field_query_value(rel, rel_class, value_part, prefix)
        return query

    def preparse_search_query_fields(self, qs, model):
        """Preparse search fields out of query text."""
        q = self.params.get("q")  # type: ignore
        if not q:
            return qs, q

        parts = shlex.split(q)
        search_query_parts = []
        field_query = Q()
        for part in parts:
            if ":" in part:
                try:
                    field_query &= self._parse_field_query(part, model)
                except Exception:
                    LOG.exception(f"Parsing field query {part}")
            elif part:
                search_query_parts.append(part)

        if field_query:
            qs = qs.filter(field_query)
        preparsed_search_query = shlex.join(search_query_parts).strip()
        return qs, preparsed_search_query

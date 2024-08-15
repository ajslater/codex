"""Parse the browser query by removing field queries and doing them with the ORM."""

import re
from decimal import Decimal
from itertools import chain
from types import MappingProxyType

from comicbox.fields.fields import IssueField
from dateparser import parse
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
from django.db.models.functions import Lower
from humanfriendly import parse_size

from codex.logger.logging import get_logger
from codex.models.comic import Comic
from codex.views.browser.filters.field import ComicFieldFilterView
from codex.views.browser.filters.search.aliases import ALIAS_FIELD_MAP, FIELD_TYPE_MAP
from codex.views.const import FALSY

_FIELD_TO_REL_SPAN_MAP = MappingProxyType(
    {
        "role": "contributors__role__name",
        "contributors": "contributors__person__name",
        "identifier": "identifier__nss",
        "identirier_type": "identifier__identifier_type__name",
        "story_arcs": "story_arc_number__story_arc__name",
    }
)
_EXCLUDE_FIELD_NAMES = frozenset({"stat", "parent_folder", "library"})
_PARSE_ISSUE_MATCHER = re.compile(r"(?P<issue_number>\d*\.?\d*)(?P<issue_suffix>.*)")

LOG = get_logger(__name__)


class BrowserFieldQueryFilter(ComicFieldFilterView):
    """Parse the browser query by removing field queries and doing them with the ORM."""

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
    def _parse_issue_values(  # noqa: PLR0913
        cls, query_dicts, rel, value, is_operator_query, query_not, to_value=None
    ):
        """Issue is not a column. Convert to issue_number and issue_suffix."""
        use_issue_number_only = is_operator_query
        issue_number_value, issue_suffix_value = cls._parse_issue_value(value)
        if issue_number_value is None:
            return
        numeric_dict = query_dicts["numeric"]
        issue_number_field = rel.replace("issue", "issue_number")
        if to_value is not None:
            to_issue_number_value, _ = cls._parse_issue_value(to_value)
            use_issue_number_only = True
            issue_number_value = (issue_number_value, to_issue_number_value)
        if issue_number_field not in query_dicts["numeric"]:
            numeric_dict[issue_number_field] = set()
        numeric_dict[issue_number_field].add((issue_number_value, query_not))

        # Suffixes are only queried if there's no leading operators.
        if not use_issue_number_only and issue_suffix_value:
            issue_suffix_field = rel.replace("issue", "issue_suffix")
            cls._parse_operator_text(
                issue_suffix_field, issue_suffix_value, query_dicts, query_not
            )

    @classmethod
    def _cast_value(cls, rel, rel_class, value):
        """Cast values by relation class."""
        """Post process special values in query_dict."""
        if rel.startswith("size"):
            value = parse_size(value)
        elif rel_class == PositiveSmallIntegerField:
            value = int(value)
        elif rel_class == DecimalField:
            value = Decimal(value)
        elif rel_class == BooleanField:
            value = value not in FALSY
        elif rel_class in (DateTimeField, DateField):
            value = parse(value)
        elif rel_class in (CharField, TextField):
            value = value.lower()
        return value

    @classmethod
    def _parse_operator(  # noqa: PLR0913
        cls, token, operator, rel, rel_class, value, query_dicts, query_not
    ):
        """Move value operator out of value into relation operator."""
        span_rel = f"{rel}__{operator}" if operator else rel
        value = value[len(token) :]
        if rel == "issue":
            cls._parse_issue_values(query_dicts, span_rel, value, True, query_not)
        else:
            value = cls._cast_value(rel, rel_class, value)
            numeric_dict = query_dicts["numeric"]
            if rel not in numeric_dict:
                numeric_dict[span_rel] = set()
            numeric_dict[span_rel].add((value, query_not))

    @classmethod
    def _parse_operator_range(  # noqa: PLR0913
        cls, token, rel, rel_class, value, query_dicts, query_not
    ):
        """Parse range operator."""
        range_from_value, range_to_value = value.split(token)
        rel = f"{rel}__range"
        if rel == ("issue__range"):
            cls._parse_issue_values(
                query_dicts,
                rel,
                range_from_value,
                True,
                query_not,
                range_to_value,
            )
        else:
            range_value = (
                (
                    cls._cast_value(rel, rel_class, range_from_value),
                    cls._cast_value(rel, rel_class, range_to_value),
                ),
                query_not,
            )
            if range_value not in query_dicts["numeric"]:
                query_dicts["numeric"][rel] = set()
            query_dicts["numeric"][rel].add(range_value)

    @staticmethod
    def _parse_field_rel(field_name, rel_class):
        """Set rel to comic attribute or relation span."""
        rel = _FIELD_TO_REL_SPAN_MAP.get(field_name, "")
        if not rel and rel_class in (ForeignKey, ManyToManyField):
            # This must be after the special span maps
            rel = field_name + "__name"

        if rel.endswith("__name"):
            rel_class = CharField

        if not rel:
            # Comic attribute
            rel = field_name

        return rel_class, rel

    def _parse_field(self, field_name: str):
        """Parse the field size of the query in to database relations."""
        if field_name in _EXCLUDE_FIELD_NAMES or (
            field_name == "path"
            and not (
                self.admin_flags["folder_view"] or self.is_admin()  # type: ignore
            )
        ):
            return None, None, False
        field_name = ALIAS_FIELD_MAP.get(field_name, field_name)
        rel_class = FIELD_TYPE_MAP.get(field_name)
        many_to_many = rel_class == ManyToManyField
        if not rel_class:
            return None, None, False

        rel_class, rel = self._parse_field_rel(field_name, rel_class)
        return rel_class, rel, many_to_many

    @staticmethod
    def _glob_to_regex(value):
        """Transform a glob into a safe regex for sqlite3."""
        # Glob to regex
        regex = False
        star_parts = value.split("*")
        if len(star_parts) <= 1:
            return value, regex

        while star_parts[0] == "*" and star_parts[-1] == "*":
            star_parts = star_parts[1:-1]

        prefix = suffix = ""

        if star_parts[0] == "*":
            star_parts = star_parts[1:]
            suffix = "$"
        elif star_parts[-1] == "*":
            star_parts = star_parts[:-1]
            prefix = "^"

        if not star_parts:
            return "", False
        if len(star_parts) == 1 and not prefix and not suffix:
            return star_parts[0], False

        escaped_star_parts = (re.escape(part) for part in star_parts)

        value = prefix + ".*".join(escaped_star_parts) + suffix
        regex = prefix or suffix or len(star_parts) > 1

        return value, regex

    @classmethod
    def _parse_operator_text(cls, rel, value, query_dicts, query_not):
        """Parse text value operators."""
        if rel == "issue":
            cls._parse_issue_values(query_dicts, rel, value, True, query_not)
            return

        value, regex = cls._glob_to_regex(value)

        dict_name = "regex" if regex else "contains"

        if rel not in query_dicts[dict_name]:
            query_dicts[dict_name][rel] = set()
        query_dicts[dict_name][rel].add((value, query_not))

    @classmethod
    def _parse_operator_numeric(cls, rel, rel_class, value, query_dicts, query_not):
        value = cls._cast_value(rel, rel_class, value)
        numeric_dict = query_dicts["numeric"]
        if rel not in numeric_dict:
            numeric_dict[rel] = set()
        numeric_dict[rel].add((value, query_not))

    @classmethod
    def _parse_field_query_value(cls, rel, rel_class, value, query_dicts):
        """Parse the operators of the value size of the field query."""
        value = value.strip()
        if value.startswith("!"):
            value = value[1:].strip()
            query_not = True
        else:
            query_not = False

        if value.startswith(">="):
            cls._parse_operator(
                ">=", "gte", rel, rel_class, value, query_dicts, query_not
            )
        elif value.startswith(">"):
            cls._parse_operator(
                ">", "gt", rel, rel_class, value, query_dicts, query_not
            )
        elif value.startswith("<="):
            cls._parse_operator(
                "<=", "lte", rel, rel_class, value, query_dicts, query_not
            )
        elif value.startswith("<"):
            cls._parse_operator(
                "<", "lt", rel, rel_class, value, query_dicts, query_not
            )
        elif "..." in value:
            cls._parse_operator_range(
                "...", rel, rel_class, value, query_dicts, query_not
            )
        elif ".." in value:
            cls._parse_operator_range(
                "..", rel, rel_class, value, query_dicts, query_not
            )
        elif rel_class in (CharField, TextField):
            cls._parse_operator_text(rel, value, query_dicts, query_not)
        else:
            cls._parse_operator_numeric(rel, rel_class, value, query_dicts, query_not)

    @classmethod
    def _optimize_text_lookups(cls, query_dicts, or_operator):
        """Optimize text lookups."""
        contains_dict = query_dicts["contains"]
        regex_dict = query_dicts["regex"]
        numeric_dict = query_dicts["numeric"]

        key_counts_dict = {}

        # Count the number of text lookups per relation.
        for key, data in chain(contains_dict.items(), regex_dict.items()):
            if key not in key_counts_dict:
                key_counts_dict[key] = 0
            key_counts_dict[key] += len(data)

        # Pop out the single contains lookups, optimal not to transform into regex
        optimized_dict = {}
        for key, count in key_counts_dict.items():
            if count == 1 and contains_dict:
                rel = key + "__icontains"
                optimized_dict[rel] = frozenset(contains_dict.pop(key))

        # Transform multiple regex and contains lookups into long regexes
        rel = ""
        optimized_regex_parts = []
        for key, data_set in chain(contains_dict.items(), regex_dict.items()):
            rel = key
            for data in data_set:
                value, query_not = data
                lookahead = "!" if query_not else ":"
                optimized_regex_parts.append(rf"(?{lookahead}{value})")

        # Set the final optimized regex in the optimized dict
        if rel:
            rel = rel + "__iregex"
            regex_operator = "|" if or_operator else ""
            optimized_regex = regex_operator.join(optimized_regex_parts)
            optimized_dict[rel] = frozenset({(optimized_regex, False)})

        optimized_dict.update(numeric_dict)
        return optimized_dict

    @staticmethod
    def _add_query_dict_to_query(query_dict, or_operator, model):
        """Convert the query dict into django orm queries."""
        prefix = "" if model == Comic else "comic__"  # type: ignore
        query = None
        for key, data_set in query_dict.items():
            rel = prefix + key
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

    def _parse_field_query(self, col, exp, model, qs):
        """Parse one field query."""
        rel_class, rel, many_to_many = self._parse_field(col)
        if not rel_class:
            LOG.debug(f"Unknown field specified in search query {col}")
            return qs, None

        if "|" in exp:
            delim = "|"
            or_operator = True
        else:
            delim = ","
            # ManyToMany char fields are forced into OR operation because AND
            # is too difficult with regex & contains
            or_operator = many_to_many and rel_class == CharField

        if rel_class in (CharField, TextField):
            lower_alias = f"lower_{col}"
            qs = qs.alias(**{lower_alias: Lower(rel)})
            rel = lower_alias

        query_dicts = {"contains": {}, "regex": {}, "numeric": {}}
        for value_part in exp.split(delim):
            self._parse_field_query_value(rel, rel_class, value_part, query_dicts)

        optimized_dict = self._optimize_text_lookups(query_dicts, or_operator)

        return qs, self._add_query_dict_to_query(optimized_dict, or_operator, model)

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

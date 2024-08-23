"""Parse field lookup right hand side expression."""

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
    TextField,
)
from django.db.models.fields import DecimalField, PositiveSmallIntegerField
from humanfriendly import parse_size

from codex.logger.logging import get_logger
from codex.views.const import FALSY

_OP_MAP = MappingProxyType({">": "gt", ">=": "gte", "<": "lt", "<=": "lte"})
_RANGE_RE = re.compile(r"\.{2,}")
_PARSE_ISSUE_MATCHER = re.compile(r"(?P<issue_number>\d*\.?\d*)(?P<issue_suffix>.*)")
_LIKE_RE = re.compile(f"([{re.escape('%_')}])")
LOG = get_logger(__name__)


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


def _parse_issue_values(rel, value, _is_operator_query, to_value=None):
    """Issue is not a column. Convert to issue_number and issue_suffix."""
    # use_issue_number_only = is_operator_query
    issue_number_value, issue_suffix_value = _parse_issue_value(value)
    if issue_number_value is None:
        return None, None
    issue_number_field = rel.replace("issue", "issue_number")
    if to_value is not None:
        to_issue_number_value, _ = _parse_issue_value(to_value)
        # use_issue_number_only = True
        issue_number_value = (issue_number_value, to_issue_number_value)

    # TODO figure out issue suffix queries
    # Suffixes are only queried if there's no leading operators.
    # if not use_issue_number_only and issue_suffix_value:
    #    issue_suffix_field = rel.replace("issue", "issue_suffix")
    #    suffix_rel, suffix_value = parse_operator_text(
    #        issue_suffix_field, issue_suffix_value
    #    )
    #    # TODO add to query

    return issue_number_field, issue_number_value


def _cast_value(rel, rel_class, value):
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
    elif rel_class in (DateField, DateTimeField):
        value = parse(value)
        if rel_class == DateField and value:
            value = value.date()
    # elif rel_class in (CharField, TextField):
    #    value = value
    return value


def _parse_operator_numeric(rel, rel_class, value):
    value = _cast_value(rel, rel_class, value)
    if value is None:
        return None, None
    return rel, value


def _parse_operator_text(rel, exp):
    """Parse text value operators."""
    if rel == "issue":
        return _parse_issue_values(rel, exp, True)

    exp = _glob_to_like(exp)
    rel += "__like"
    return rel, exp


def _parse_operator(operator, rel, rel_class, exp):
    """Move value operator out of value into relation operator."""
    lookup = _OP_MAP[operator]
    span_rel = f"{rel}__{lookup}" if operator else rel
    value = exp[len(operator) :]
    if rel == "issue":
        return _parse_issue_values(span_rel, value, True)
    return _parse_operator_numeric(span_rel, rel_class, value)


def _parse_operator_range(rel, rel_class, value):
    """Parse range operator."""
    range_from_value, range_to_value = _RANGE_RE.split(value, 1)
    rel = f"{rel}__range"
    if rel == ("issue__range"):
        return _parse_issue_values(
            rel,
            range_from_value,
            True,
            range_to_value,
        )
    range_value = (
        _cast_value(rel, rel_class, range_from_value),
        _cast_value(rel, rel_class, range_to_value),
    )
    return rel, range_value


def _glob_to_like(value) -> str:
    """Transform globs into like lookups."""
    # Escape like tokens
    # value = _LIKE_RE.sub(lambda match: f"\\{match.group()}", value)
    value = _LIKE_RE.sub(r"\\\g<1>", value)

    # value = value.replace("%", r"\%")  # TODO faster with regex
    # value = value.replace("_", r"\_")

    # Remove double stars
    while True:
        new_value = value.replace("**", "*")
        if new_value == value:
            value = new_value
            break
        value = new_value

    # Replace starts with like operands
    value = value.replace("*", "%")

    # If not a prefix or suffix search, make a like term search
    if not value.startswith("%") and not value.endswith("%"):
        value = f"%{value}%"

    return value


def parse_expression(rel, rel_class, exp):
    """Parse the operators of the value size of the field query."""
    for op in _OP_MAP:
        if exp.startswith(op):
            q = _parse_operator(
                op,
                rel,
                rel_class,
                exp,
            )
            break
    else:
        if ".." in exp:
            q = _parse_operator_range(rel, rel_class, exp)
        elif rel_class in (CharField, TextField) and not rel.startswith("volume"):
            q = _parse_operator_text(rel, exp)
        else:
            q = _parse_operator_numeric(rel, rel_class, exp)
    # print(q)
    return q


###########################
# OPTIMIZE STRING LOOKUPS #
###########################
def _glob_to_regex(value):
    """Transform a glob into a safe regex for sqlite3."""
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


def optimize_text_lookups(query_dicts, or_operator):
    """Optimize text lookups."""
    like_dict = query_dicts["like"]
    regex_dict = query_dicts["regex"]
    numeric_dict = query_dicts["numeric"]

    key_counts_dict = {}

    # Count the number of text lookups per relation.
    for key, data in chain(like_dict.items(), regex_dict.items()):
        if key not in key_counts_dict:
            key_counts_dict[key] = 0
        key_counts_dict[key] += len(data)

    # Pop out the single like lookups, optimal not to transform into regex
    optimized_dict = {}
    for key, count in key_counts_dict.items():
        if count == 1 and like_dict:
            rel = key + "__like"
            optimized_dict[rel] = frozenset(like_dict.pop(key))

    # Transform multiple regex and like lookups into long regexes
    rel = ""
    optimized_regex_parts = []
    for key, data_set in chain(like_dict.items(), regex_dict.items()):
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

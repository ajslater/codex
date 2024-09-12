"""Parse field lookup right hand side expression."""

import re
from decimal import Decimal
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
from codex.settings.settings import FALSY

_QUOTES_RE = re.compile(r"[\"']")
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
    numeric_value = Decimal(matches.group("issue_number"))
    suffix_value = matches.group("issue_suffix")
    return numeric_value, suffix_value


def _parse_issue_values(rel, value, to_value=None):
    """Issue is not a column. Convert to issue_number and issue_suffix."""
    numeric_value, suffix_value = _parse_issue_value(value)
    if to_value is not None:
        to_numeric_value, to_suffix_value = _parse_issue_value(to_value)
    else:
        to_numeric_value = to_suffix_value = None

    q_dict = {}

    if numeric_value is not None:
        issue_number_field = rel.replace("issue", "issue_number")
        if to_numeric_value is not None:
            numeric_value = (numeric_value, to_numeric_value)
        q_dict[issue_number_field] = numeric_value

    if suffix_value is not None:
        issue_suffix_field = rel.replace("issue", "issue_suffix")
        if to_suffix_value is not None:
            suffix_value = (suffix_value, to_suffix_value)
        q_dict[issue_suffix_field] = suffix_value

    return q_dict


def _cast_value(rel, rel_class, value):
    """Cast values by relation class."""
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
        return {}
    return {rel: value}


def _parse_operator_text(rel, exp):
    """Parse text value operators."""
    if rel == "issue":
        return _parse_issue_values(rel, exp)

    value = _glob_to_like(exp)
    rel += "__like"
    return {rel: value}


def _parse_operator(operator, rel, rel_class, exp):
    """Move value operator out of value into relation operator."""
    lookup = _OP_MAP[operator]
    span_rel = f"{rel}__{lookup}" if operator else rel
    value = exp[len(operator) :]
    if rel == "issue":
        return _parse_issue_values(span_rel, value)
    return _parse_operator_numeric(span_rel, rel_class, value)


def _parse_operator_range(rel, rel_class, value) -> dict:
    """Parse range operator."""
    range_from_value, range_to_value = _RANGE_RE.split(value, 1)
    rel = f"{rel}__range"
    if rel == ("issue__range"):
        return _parse_issue_values(
            rel,
            range_from_value,
            range_to_value,
        )
    range_value = (
        _cast_value(rel, rel_class, range_from_value),
        _cast_value(rel, rel_class, range_to_value),
    )
    return {rel: range_value}


def _glob_to_like(value) -> str:
    """Transform globs into like lookups."""
    # Escape like tokens
    value = _LIKE_RE.sub(r"\\\g<1>", value)

    # Remove double stars
    while True:
        new_value = value.replace("**", "*")
        if new_value == value:
            value = new_value
            break
        value = new_value

    if not value:
        return "%"

    # Replace starts with like operands
    value = value.replace("*", "%")

    # If not a prefix or suffix search, make a like term search
    if not value.startswith("%") and not value.endswith("%"):
        value = f"%{value}%"

    return value


def parse_expression(rel, rel_class, exp) -> dict:
    """Parse the operators of the value size of the field query."""
    exp = _QUOTES_RE.sub("", exp)

    for op in _OP_MAP:
        if exp.startswith(op):
            q_dict = _parse_operator(
                op,
                rel,
                rel_class,
                exp,
            )
            break
    else:
        if ".." in exp:
            q_dict = _parse_operator_range(rel, rel_class, exp)
        elif rel_class in (CharField, TextField) and not rel.startswith("volume"):
            q_dict = _parse_operator_text(rel, exp)
        else:
            q_dict = _parse_operator_numeric(rel, rel_class, exp)
    return q_dict

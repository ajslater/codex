"""Optimize Text Lookups."""

import re

from django.db.models import Q

# Just an unlikely character
_PERCENT_PLACEHOLDER = "Ɍ"


def _like_to_regex(like):
    """Transform a glob into a safe regex for sqlite3."""
    # unescape like
    like = like.replace(r"\%", _PERCENT_PLACEHOLDER)
    like = like.replace(r"\_", "_")

    while like[0] == "%" and like[-1] == "%":
        like = like[1:-1]

    parts = like

    prefix = suffix = ""

    if parts[0] == "%":
        parts = parts[1:]
        suffix = "$"
    elif parts[-1] == "%":
        parts = parts[:-1]
        prefix = "^"

    if not parts:
        return parts

    regex = parts.replace(_PERCENT_PLACEHOLDER, "%")
    regex = re.escape(regex)
    regex = regex.replace("%", ".*")

    return prefix + regex + suffix


def like_qs_to_regex_q(q: Q, regex_op: str, many_to_many: bool):
    """Optimize a tree of like lookup qs to one regex q."""
    regexes = []
    # Optimize like equations into regexes
    rel = ""

    if many_to_many:
        regex_op = "|"

    lookahead = "!" if q.negated else ":" if regex_op == "|" else "="
    for child_q in q.children:
        rel, like = child_q
        value = _like_to_regex(like)
        if lookahead == "=":
            value = ".*" + value + ".*"
        regex = rf"(?{lookahead}{value})"
        regexes.append(regex)
    regex_value = regex_op.join(regexes)
    if lookahead == "=":
        regex_value = ".*" + regex_value + ".*"

    rel = rel.replace("like", "iregex")
    q = Q(**{rel: regex_value})
    print(q)
    return q

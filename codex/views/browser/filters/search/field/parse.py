"""Parse field boolean expressions into Django ORM Queries."""

import copy
import re
from functools import lru_cache
from typing import Any

from django.db.models import Q
from lark import Lark, Token, Transformer, Tree

from codex.models.base import MAX_NAME_LEN, BaseModel
from codex.models.comic import Comic
from codex.views.browser.filters.search.field.expression import parse_expression

_QUOTES_REXP = r"""(?:\".*?\")"""
_OPERATORS_REXP = "and not|or not|and|or"
_BEGIN_NOT_REXP = r"^\s*\(?\s*(?P<not>not)"
_IMPLICIT_AND_REXP = (
    rf"""{_QUOTES_REXP}|\ (?P<ok>{_OPERATORS_REXP})\ |(?P<bare>(?:\ not)?\ )\S"""
)
_BEGIN_NOT_RE = re.compile(_BEGIN_NOT_REXP, flags=re.IGNORECASE)
_IMPLICIT_AND_RE = re.compile(_IMPLICIT_AND_REXP, flags=re.IGNORECASE)

_GRAMMAR = (
    r"""
    ?start: or_expr

    ?or_expr: and_expr (OR and_expr)*
    ?and_expr: not_expr (AND not_expr)*
    ?not_expr: NOT not_expr -> not_op
             | atom
    ?atom: "(" or_expr ")"
         | QUOTED
         | WORD

    OR: /or/i
    AND: /and/i
    NOT: /not/i

    QUOTED: "\"" /[^"]*/ "\""
    WORD: /[^\s()",]{1,"""
    + str(MAX_NAME_LEN)
    + r"""}/

    %ignore /\s+/
"""
)
PARSER = Lark(_GRAMMAR, parser="lalr", maybe_placeholders=False)


class FieldQueryTransformer(Transformer):
    """Transform parse tree into Django Q objects."""

    def __init__(
        self,
        rel: str,
        rel_class: type,
        model: type,
        *,
        many_to_many: bool,
    ) -> None:
        """Initialize context."""
        super().__init__()
        self._rel = rel
        self._rel_class = rel_class
        self._model = model
        self._many_to_many = many_to_many

    def _prefix_q_dict(self, q_dict: dict) -> dict:
        """Add or subtract relation prefixes to q_dict for the model."""
        prefix = "" if self._model == Comic else "comic__"
        model_span = self._model.__name__.lower() + "__"
        prefixed_q_dict = {}
        for parsed_rel, value in q_dict.items():
            prefixed_rel = (
                parsed_rel.removeprefix(model_span)
                if parsed_rel.startswith(model_span)
                else prefix + parsed_rel
            )
            prefixed_q_dict[prefixed_rel] = value
        return prefixed_q_dict

    def _make_operand_q(self, token: Token) -> Q:
        """Construct Django ORM Query from a leaf operand value."""
        if (q_dict := parse_expression(self._rel, self._rel_class, str(token))) and (
            prefixed_q_dict := self._prefix_q_dict(q_dict)
        ):
            return Q(**prefixed_q_dict)
        return Q()

    def QUOTED(self, token: Token) -> Q:  # noqa: N802
        """Handle quoted string operand."""
        return self._make_operand_q(token)

    def WORD(self, token: Token) -> Q:  # noqa: N802
        """Handle bare word operand."""
        return self._make_operand_q(token)

    def not_op(self, args: list[Any]) -> Q:
        """Negate the child query."""
        return ~args[0]

    def or_expr(self, args: list[Any]) -> Q:
        """Combine children with OR."""
        q = Q()
        for arg in args:
            if isinstance(arg, Q):
                q |= arg
        return q

    def and_expr(self, args: list[Any]) -> Q:
        """Combine children with AND."""
        q = Q()
        for arg in args:
            if isinstance(arg, Q):
                q &= arg
        return q


@lru_cache(maxsize=512)
def _build_field_query(
    rel: str,
    rel_class: type,
    exp: str,
    model: type[BaseModel],
    *,
    many_to_many: bool,
) -> Q:
    """Build the Q tree for a field:expression pair. Cached."""
    # Allow negative column search
    begin_not_match = _BEGIN_NOT_RE.search(exp)
    if begin_not_match:
        start = begin_not_match.start("not")
        exp = exp[:start] + '"" and ' + exp[start:]

    # Add implicit and for the parser
    exp = _IMPLICIT_AND_RE.sub(
        lambda m: f" and{m.group(0)}" if m.group("bare") else m.group(0), exp
    )

    tree: Tree = PARSER.parse(exp)
    transformer = FieldQueryTransformer(
        rel, rel_class, model, many_to_many=many_to_many
    )
    return transformer.transform(tree)


def get_field_query(
    rel: str,
    rel_class: type,
    exp: str,
    model: type[BaseModel],
    *,
    many_to_many: bool,
) -> Q:
    """
    Convert rel and text expression into queries.

    Returns a ``copy.deepcopy`` of the cached Q tree because downstream
    callers (``_hoist_filters``) mutate ``child.negated`` on the returned
    tree's children.
    """
    cached = _build_field_query(rel, rel_class, exp, model, many_to_many=many_to_many)
    return copy.deepcopy(cached)

"""Parse field boolean expressions into Django ORM Queries."""

import re
from typing import TYPE_CHECKING

from django.db.models import Q
from pyparsing import (
    CaselessLiteral,
    OpAssoc,
    ParserElement,
    QuotedString,
    Word,
    infix_notation,
    printables,
)

from codex.models.base import MAX_NAME_LEN
from codex.models.comic import Comic
from codex.views.browser.filters.search.field.expression import parse_expression

if TYPE_CHECKING:
    from pyparsing.helpers import InfixNotationOperatorSpec

_QUOTES_REXP = r"(?:\".*?\")"
_OPERATORS_REXP = "|".join(("and not", "or not", "and", "or"))
_BEGIN_NOT_REXP = r"^\s*\(?\s*(?P<not>not)"
_IMPLICIT_AND_REXP = (
    rf"{_QUOTES_REXP}|\ (?P<ok>{_OPERATORS_REXP})\ |(?P<bare>(?:\ not)?\ )\S"
)
_BEGIN_NOT_RE = re.compile(_BEGIN_NOT_REXP, flags=re.IGNORECASE)
_IMPLICIT_AND_RE = re.compile(_IMPLICIT_AND_REXP, flags=re.IGNORECASE)
ParserElement.enablePackrat()


class BoolOperand:
    """Hacky Base for injecting rel."""

    def __init__(self, tokens, context):
        """Initialize value from first token."""
        self.value = tokens[0]
        self.context = context

    def __repr__(self) -> str:
        """Represent as string."""
        return str(self.value)

    def _prefix_q_dict(self, q_dict):
        """Add (or subtract!) relation prefixes to q_dict for the model."""
        model = self.context[2]
        prefix = "" if model == Comic else "comic__"
        model_span = model.__name__.lower() + "__"
        prefixed_q_dict = {}
        for parsed_rel, value in q_dict.items():
            prefixed_rel = (
                parsed_rel.removeprefix(model_span)
                if parsed_rel.startswith(model_span)
                else prefix + parsed_rel
            )
            prefixed_q_dict[prefixed_rel] = value
        return prefixed_q_dict

    def to_query(self) -> Q:
        """Construct Django ORM Query from rel & value."""
        rel = self.context[0]
        rel_class = self.context[1]
        q_dict = parse_expression(rel, rel_class, self.value)
        if not q_dict:
            return Q()

        prefixed_q_dict = self._prefix_q_dict(q_dict)

        return Q(**prefixed_q_dict)


class BoolNot(BoolOperand):
    """NOT Operand."""

    def __init__(self, tokens, context):
        """Initialize args from first token."""
        self.arg = tokens[0][1]
        self.context = context

    def __repr__(self) -> str:
        """Represent as string."""
        return f"NOT {self.arg}"

    def to_query(self) -> Q:
        """Negate argument query."""
        q = self.arg.to_query()
        return ~q


class BoolBinaryOperand:
    """Boolean Binary Operand."""

    OP: str = ""

    def __init__(self, tokens, context):
        """Initialize args from first two tokens."""
        self.args = tokens[0][0::2]
        self.context = context

    def __repr__(self) -> str:
        """Represent as string."""
        sep = f" {self.OP} "
        return f"({sep.join(map(str, self.args))})"

    def to_query(self) -> Q:
        """Construct Django ORM Query from args."""
        q = Q()

        for arg in self.args:
            arg_q = arg.to_query()
            if self.OP == Q.AND:
                q &= arg_q
            else:
                q |= arg_q

        return q


class BoolAnd(BoolBinaryOperand):
    """AND Operand."""

    OP = Q.AND


class BoolOr(BoolBinaryOperand):
    """OR Operand."""

    OP = Q.OR


def _get_context_operand(op_class, context):
    """Hack context into operands."""

    def parse_action(_s, _loc, toks):
        """Inject context into operand classes."""
        return op_class(toks, context)

    return parse_action


def _create_context_expression(context):
    # I can't find a way for pyparsing to inject context after the grammar is defined.
    bool_operand_fn = _get_context_operand(BoolOperand, context)
    bool_not_operand_fn = _get_context_operand(BoolNot, context)
    bool_and_operand_fn = _get_context_operand(BoolAnd, context)
    bool_or_operand_fn = _get_context_operand(BoolOr, context)

    # Order is important for operands so quoted strings get parsed first
    bool_operand = QuotedString('"') | Word(
        printables, exclude_chars="(),", max=MAX_NAME_LEN
    )
    bool_operand.set_parse_action(bool_operand_fn)
    bool_operand.set_name("boolean_operand")
    op_list: list[InfixNotationOperatorSpec] = [
        # In order of precedence
        (CaselessLiteral("not"), 1, OpAssoc.RIGHT, bool_not_operand_fn),
        (CaselessLiteral("and"), 2, OpAssoc.LEFT, bool_and_operand_fn),
        (CaselessLiteral("or"), 2, OpAssoc.LEFT, bool_or_operand_fn),
    ]

    bool_expr = infix_notation(bool_operand, op_list)
    bool_expr.set_name("boolean_expression")
    return bool_expr


def get_field_query(rel, rel_class, exp, model, many_to_many):
    """Convert rel and text expression into queries."""
    # Allow negative column search
    begin_not_match = _BEGIN_NOT_RE.search(exp)
    if begin_not_match:
        start = begin_not_match.start("not")
        exp = exp[:start] + '"" and ' + exp[start:]

    # Add implicit and for the parser
    exp = _IMPLICIT_AND_RE.sub(
        lambda m: f" and{m.group(0)}" if m.group("bare") else m.group(0), exp
    )

    context = rel, rel_class, model, many_to_many
    bool_expr = _create_context_expression(context)

    parsed_result = bool_expr.parse_string(exp)
    root_bool_operand: BoolOperand = parsed_result[0]  # type:ignore
    return root_bool_operand.to_query()

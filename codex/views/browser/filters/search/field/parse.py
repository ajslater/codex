"""Parse field boolean expressions into Django ORM Queries."""

import re

from django.db.models import Q
from django.db.models.fields import Field
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
from codex.models.groups import BrowserGroupModel
from codex.views.browser.filters.search.field.expression import parse_expression

_OPERATORS_REXP = "(" + "|".join(("and not", "or not", "and", "or", "not")) + ")"
_IMPLICIT_AND_RE = re.compile(
    rf"(?:\".*?\")|(?:\s{_OPERATORS_REXP}\s)|(?P<bare>\ )\S",
    flags=re.IGNORECASE,
)
_BARE_NOT_RE = re.compile(
    r"\b(?P<ok>(and|or)\snot)|(?P<bare>not)\b", flags=re.IGNORECASE
)
ParserElement.enablePackrat()


def to_dict(rel, rel_class, exp) -> dict:
    """Get query dict for expression."""
    return parse_expression(rel, rel_class, exp)


def to_query(
    rel: str, rel_class: type[Field], model: type[BrowserGroupModel], exp: str
) -> Q:
    """Construct Django ORM Query from rel & value."""
    q_dict = to_dict(rel, rel_class, exp)
    if not q_dict:
        return Q()

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
    return Q(**prefixed_q_dict)


class BoolOperand:
    """Hacky Base for injecting rel."""

    rel: str = ""
    rel_class: type[Field] = Field
    model: type[BrowserGroupModel]
    many_to_many: bool = False

    def __init__(self, tokens):
        """Initialize value from first token."""
        self.value = tokens[0]

    def __repr__(self) -> str:
        """Represent as string."""
        return self.value

    def to_query(self) -> Q:
        """Construct Django ORM Query from rel & value."""
        return to_query(self.rel, self.rel_class, self.model, self.value)


class BoolBinaryOperand:
    """Boolean Binary Operand."""

    OP: str = ""

    def __init__(self, tokens):
        """Initialize args from first two tokens."""
        self.args = tokens[0][0::2]

    def __repr__(self) -> str:
        """Represent as string."""
        sep = f" {self.OP} "
        return f"({sep.join(map(str, self.args))})"

    def to_query(self) -> Q:
        """Construct Django ORM Query from args."""
        q = Q()

        nots = []
        many_to_many = False
        for arg in self.args:
            arg_q = arg.to_query()
            if arg_q.negated:
                many_to_many |= arg.many_to_many
                nots.append(~arg_q)
            else:
                # op = Q.OR if arg.many_to_many else self.OP
                op = self.OP
                if op == Q.AND:
                    q &= arg_q
                else:
                    q |= arg_q

        if nots:
            not_q = Q()
            not_op = Q.OR if many_to_many or self.OP == Q.AND else Q.AND
            for not_arg_q in nots:
                if not_op == Q.AND:
                    not_q &= not_arg_q
                else:
                    not_q |= not_arg_q

            not_q = ~not_q
            if self.OP == Q.AND:
                q &= not_q
            else:
                q |= not_q

        return q


class BoolNot:  # (BoolRelOperandBase):
    """NOT Operand."""

    def __init__(self, tokens):
        """Initialize args from first token."""
        self.arg = tokens[0][1]

    def __repr__(self) -> str:
        """Represent as string."""
        return f"NOT {self.arg}"

    def to_query(self) -> Q:
        """Negate argument query."""
        q = self.arg.to_query()
        return ~q


class BoolAnd(BoolBinaryOperand):
    """AND Operand."""

    OP = Q.AND


class BoolOr(BoolBinaryOperand):
    """OR Operand."""

    OP = Q.OR


def _get_bool_op_rel(
    op_class, span: str, rel_cls: type[Field], mdl: type[BrowserGroupModel], m2m: bool
):
    """Hack rel into Bool."""
    return type(
        op_class.__name__ + "Inject",
        (op_class,),
        {"rel": span, "rel_class": rel_cls, "model": mdl, "many_to_many": m2m},
    )


def gen_query(rel, rel_class, exp, model, many_to_many):
    """Convert rel and text expression into queries."""
    # TODO BoolOperand() needs to use field parse value.

    # TODO BARE_NOT could be handled by IMPLICIT_AND
    exp = _BARE_NOT_RE.sub(
        lambda m: "and not" if m.group("bare") else m.group("ok"), exp
    )
    exp = _IMPLICIT_AND_RE.sub(
        lambda m: f" and{m.group(0)}" if m.group("bare") else m.group(0), exp
    )

    # HACK this could be defined once on startup if I could figure out how to inject rel to infix_notation
    bool_operand_class = _get_bool_op_rel(
        BoolOperand, rel, rel_class, model, many_to_many
    )

    # Order is important here so quoted strings get parsed first
    bool_operand = QuotedString('"') | Word(
        printables, exclude_chars="(),", max=MAX_NAME_LEN
    )
    bool_operand.setParseAction(bool_operand_class).setName("bool_operand")

    bool_expr = infix_notation(
        bool_operand,
        [
            (
                CaselessLiteral("not"),
                1,
                OpAssoc.RIGHT,
                _get_bool_op_rel(BoolNot, rel, rel_class, model, many_to_many),
            ),
            (CaselessLiteral("and"), 2, OpAssoc.LEFT, BoolAnd),
            (CaselessLiteral("or"), 2, OpAssoc.LEFT, BoolOr),
        ],
    ).setName("boolean_expression")

    # TODO inject rel, rel_class, model into parseString or to_query()  instead of in infix and bool_operand.
    # print(exp)
    parsed_result = bool_expr.parseString(exp)
    #  print(parsed_result.as_list(), parsed_result.as_dict())
    root_bool_operand: BoolOperand = parsed_result[0]  # type:ignore
    return root_bool_operand.to_query()


# if __name__ == "__main__":
# import sys
#
# from django.db.models import CharField
# exp = " ".join(sys.argv[1:])
# print(f"{exp=}")
# q = gen_query("path", CharField, exp, Comic, False)
# print(q)

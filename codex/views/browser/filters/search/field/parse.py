"""Parse field boolean expressions into Django ORM Queries."""

import re

from django.db.models import Q
from django.db.models.fields import Field
from pyparsing import (
    Keyword,
    OpAssoc,
    ParserElement,
    Word,
    infix_notation,
    printables,
)

from codex.models.comic import Comic
from codex.models.groups import BrowserGroupModel
from codex.views.browser.filters.search.field.expression import parse_expression

_BARE_NOT_RE = re.compile(r"\b(?P<ok>(and|or)\snot)|(?P<bare>not)\b")
ParserElement.enablePackrat()


def to_query(rel, rel_class, exp, model) -> Q:
    """Construct Django ORM Query from rel & value."""
    q_dict = parse_expression(rel, rel_class, exp)
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


class BoolRelOperandBase:
    """Hacky Base for injecting rel."""

    rel: str = ""
    rel_class: type[Field] = Field
    model: type[BrowserGroupModel]


class BoolOperand(BoolRelOperandBase):
    """Boolean Operand Base."""

    def __init__(self, tokens):
        """Initialize value from first token."""
        self.value = tokens[0]

    def __repr__(self) -> str:
        """Represent as string."""
        return self.value

    def to_query(self) -> Q:
        """Construct Django ORM Query from rel & value."""
        return to_query(self.rel, self.rel_class, self.value, self.model)


class BoolBinaryOperand:
    """Boolean Binary Operand."""

    repr_symbol: str = ""
    OP = ""

    def __init__(self, tokens):
        """Initialize args from first two tokens."""
        self.args = tokens[0][0::2]

    def __repr__(self) -> str:
        """Represent as string."""
        sep = f" {self.repr_symbol} "
        return f"({sep.join(map(str, self.args))})"

    def to_query(self) -> Q:
        """Construct Django ORM Query from args."""
        q = Q()
        for arg in self.args:
            arg_q = arg.to_query()
            q = q._combine(arg_q, self.OP)  # noqa: SLF001, pyright: reportPrivateUsage=false

        # TODO add text optimization in here
        # if self.rel_class in (CharField, TextField):
        # if q.children[0][0]
        # optimized_dict = optimize_text_lookups(query_dicts)

        return q


class BoolNot(BoolRelOperandBase):
    """NOT Operand."""

    def __init__(self, tokens):
        """Initialize args from first token."""
        self.arg = tokens[0][1]

    def __repr__(self) -> str:
        """Represent as string."""
        return f"~{self.arg}"

    def to_query(self) -> Q:
        """Construct Django ORM Query from args."""
        # TODO unused conditions.
        if isinstance(self.arg, Q):
            # print(40*"*" +"NOT Q" + 40 *"*")
            q = self.arg
        elif not isinstance(self.arg, str):
            # Happens
            # print("NOT {self.arg=} to_query()")
            q = self.arg.to_query()
        else:
            # print(40*"*" +"NOT value" + 40*"*")
            q = to_query(self.rel, self.rel_class, self.arg, self.model)

        return ~q


class BoolAnd(BoolBinaryOperand):
    """AND Operand."""

    repr_symbol = "&"
    OP = Q.AND


class BoolOr(BoolBinaryOperand):
    """OR Operand."""

    repr_symbol = "|"
    OP = Q.OR


def _get_bool_op_rel(
    op_class, span: str, rel_cls: type[Field], mdl: type[BrowserGroupModel]
):
    """Hack rel into Bool."""
    return type(
        op_class.__name__ + "Inject",
        (op_class,),
        {"rel": span, "rel_class": rel_cls, "model": mdl},
    )


def gen_query(rel, rel_class, exp, model):
    """Convert rel and text expression into queries."""
    # TODO BoolOperand() needs to use field parse value.

    exp = _BARE_NOT_RE.sub(lambda m: "and not" if m.group("bare") else "not", exp)

    # HACK this could be defined once on startup if I could figure out how to inject rel to infix_notation
    bool_operand_class = _get_bool_op_rel(BoolOperand, rel, rel_class, model)

    # bool_operand = CharsNotIn("()\"' ", max=128)
    bool_operand = Word(printables, exclude_chars="()\"' ", max=128)
    bool_operand.setParseAction(bool_operand_class).setName("bool_operand")

    bool_expr = infix_notation(
        bool_operand,
        [
            (
                Keyword("not"),
                1,
                OpAssoc.RIGHT,
                _get_bool_op_rel(BoolNot, rel, rel_class, model),
            ),
            (Keyword("and"), 2, OpAssoc.LEFT, BoolAnd),
            (Keyword("or"), 2, OpAssoc.LEFT, BoolOr),
        ],
    ).setName("boolean_expression")

    exp = exp.lower()
    # TODO inject rel, rel_class, model into parseString or to_query()  instead of in infix and bool_operand.
    # print(f"{exp=}")
    parsed_result = bool_expr.parseString(exp)
    # print(f"{parsed_result=}")
    return parsed_result[0].to_query()

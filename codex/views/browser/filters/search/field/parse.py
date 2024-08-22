"""Parse field boolean expressions into Django ORM Queries."""

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

NOT = Keyword("not")
AND = Keyword("and")
OR = Keyword("or")


ParserElement.enablePackrat()


def to_dict(rel, rel_class, value) -> dict:
    """Construct query dict from rel & value."""
    # TODO make parse expression return query_dict or something like it
    query_dict = {}
    parse_expression(rel, rel_class, value, query_dict)
    return query_dict


def to_query(rel, rel_class, value, model) -> Q:
    """Construct Django ORM Query from rel & value."""
    query_dict = to_dict(rel, rel_class, value)

    # for values in query_dicts.values():
    #    if values:
    #        query_dict = values
    #        break
    # else:
    #    query_dict = {}

    # TODO don't pass model to to_dict
    # add prefixes here.

    prefixed_query_dict = {}

    prefix = "" if model == Comic else "comic__"
    model_span = model.__name__.lower() + "__"
    query_not = False
    for key, final_value in query_dict.items():
        prefixed_rel = (
            key.removeprefix(model_span) if key.startswith(model_span) else prefix + key
        )
        # TODO no more sets and query_not
        for final_value_element in final_value:
            if isinstance(final_value_element, tuple):
                real_final_value, query_not = final_value_element
            else:
                real_final_value = final_value_element
            prefixed_query_dict[prefixed_rel] = real_final_value

    # TODO test that query_dict is always one key for query_not
    # or eliminate query not.
    return ~Q(**prefixed_query_dict) if query_not else Q(**prefixed_query_dict)


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

    # def to_dict(self) -> dict:
    #    """Construct query dict from rel & value."""
    #    return to_dict(self.rel, self.rel_class, self.value)


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

    # def to_dict(self) -> dict:
    #    """Construct query dict from rel & value."""
    #    all_query_dicts = {}
    #    for arg in self.args:
    #        query_dict = arg.to_dict()
    #        # TODO either this needs to combine with self.OP
    #        #   OR it needs to go away and just extract children for optimization in to_query.
    #        #   The latter is sounding simpler right now.
    #        for key, value in query_dict.items():
    #           all_query_dicts[key].update(value)
    #    return all_query_dicts

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
        elif isinstance(self.arg, BoolBinaryOperand | BoolNot):
            # Happens
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

    class BoolOperandWithRel(op_class):
        rel: str = span
        rel_class: type[Field] = rel_cls
        model: type[BrowserGroupModel] = mdl

    return BoolOperandWithRel


def gen_query(rel, rel_class, exp, model):
    """Convert rel and text expression into queries."""
    # TODO BoolOperand() needs to use field parse value.

    # HACK this could be defined once on startup if I could figure out how to inject rel to infix_notation
    bool_operand_class = _get_bool_op_rel(BoolOperand, rel, rel_class, model)

    # bool_operand = CharsNotIn("()\"' ", max=128)
    bool_operand = Word(printables, exclude_chars="()\"' ", max=128)
    bool_operand.setParseAction(bool_operand_class).setName("bool_operand")

    bool_expr = infix_notation(
        bool_operand,
        [
            (NOT, 1, OpAssoc.RIGHT, _get_bool_op_rel(BoolNot, rel, rel_class, model)),
            (AND, 2, OpAssoc.LEFT, BoolAnd),
            (OR, 2, OpAssoc.LEFT, BoolOr),
        ],
    ).setName("boolean_expression")

    exp = exp.lower()
    parsed = bool_expr.parseString(exp)
    return parsed[0].to_query()

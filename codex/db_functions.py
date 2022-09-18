"""Custom Django DB functions."""
from django.db.models import Aggregate
from django.db.models.fields import CharField


class GroupConcat(Aggregate):
    """Sqlite3 group_concat() function."""

    function = "GROUP_CONCAT"
    template = "%(function)s(%(distinct)s %(expressions)s)"
    allow_distinct = True

    def __init__(self, expressions, distinct=False, separator=",", **extra):
        """Pass along the params."""
        super().__init__(
            expressions,
            distinct=distinct,
            separator=separator,
            output_field=CharField(),
            **extra,
        )

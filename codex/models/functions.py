"""Custom Django DB functions."""

from django.db.models.aggregates import Aggregate
from django.db.models.expressions import Func
from django.db.models.fields import CharField, FloatField, TextField
from django.db.models.fields.json import JSONField
from django.db.models.fields.related import OneToOneField
from django.db.models.lookups import Lookup
from typing_extensions import override

from codex.models.fields import CleaningCharField, CleaningTextField


class JsonGroupArray(Aggregate):
    """Sqlite3 JSON_GROUP_ARRAY function."""

    allow_distinct = True
    function = "JSON_GROUP_ARRAY"
    name = "JsonGroupArray"

    def __init__(self, *args, **kwargs):
        """output_field is set in the constructor."""
        super().__init__(*args, output_field=JSONField(), **kwargs)


class GroupConcat(Aggregate):
    """Sqlite3 GROUP_CONCAT."""

    # Defaults to " " separator which is all I need for now.

    allow_distinct = True
    allow_order_by = True
    function = "GROUP_CONCAT"
    name = "GroupConcat"

    def __init__(self, *args, **kwargs):
        """output_field is set in the constructor."""
        super().__init__(*args, output_field=CharField(), **kwargs)


@OneToOneField.register_lookup
class FTS5Match(Lookup):
    """Sqlite3 FTS5 MATCH lookup."""

    lookup_name = "match"

    @override
    def as_sql(self, compiler, connection):
        """Generate MATCH sql."""
        rhs, rhs_params = self.process_rhs(compiler, connection)
        # MATCH works on the table itself not the one_to_one rel.
        # Force the table name without substitutions by the optimizer
        sql = "codex_comicfts MATCH " + rhs
        params = rhs_params
        return sql, params


@CharField.register_lookup
@TextField.register_lookup
@CleaningCharField.register_lookup
@CleaningTextField.register_lookup
class Like(Lookup):
    """SQL LIKE lookup."""

    lookup_name = "like"
    prepare_rhs = False

    @override
    def as_sql(self, compiler, connection):
        """Generate LIKE sql."""
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        sql = f"{lhs} LIKE {rhs}"
        return sql, params


class ComicFTSRank(Func):
    """Sqlite3 FTS5 inverse rank function."""

    function = "rank"
    template = '("codex_comicfts"."rank" * -1)'

    def __init__(self, *args, **kwargs):
        """output_field is set in the constructor."""
        super().__init__(*args, output_field=FloatField(), **kwargs)

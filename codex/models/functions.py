"""Custom Django DB functions."""

from django.db.models.aggregates import Aggregate
from django.db.models.expressions import Func
from django.db.models.fields import CharField, FloatField, TextField
from django.db.models.fields.json import JSONField
from django.db.models.fields.related import OneToOneField
from django.db.models.lookups import Lookup


class JsonGroupArray(Aggregate):
    """Sqlite3 JSON_GROUP_ARRAY function."""

    allow_distinct = True
    function = "JSON_GROUP_ARRAY"
    name = "JsonGroupArray"
    output_field = JSONField()  # type: ignore


class GroupConcat(Aggregate):
    """Sqlite3 GROUP_CONCAT."""

    # Defaults to " " separator which is all I need for now.

    allow_distinct = True
    function = "GROUP_CONCAT"
    name = "GroupConcat"
    output_field = CharField()  # type: ignore


@OneToOneField.register_lookup
class FTS5Match(Lookup):
    """Sqlite3 FTS5 MATCH lookup."""

    lookup_name = "match"

    def as_sql(self, compiler, connection):
        """Generate MATCH sql."""
        # lhs, lhs_params = self.process_lhs(compiler, connection)
        # fts_table = lhs.split(".")[0]
        rhs, rhs_params = self.process_rhs(compiler, connection)
        # MATCH works on the table itself not the one_to_one rel.
        # Force the table name without substitutions by the optimizer
        sql = "codex_comicfts MATCH " + rhs
        params = rhs_params
        return sql, params


@CharField.register_lookup
@TextField.register_lookup
class Like(Lookup):
    """SQL LIKE lookup."""

    lookup_name = "like"

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
    output_field = FloatField()  # type: ignore

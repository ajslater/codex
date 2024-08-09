"""Custom Django DB functions."""

from django.db.models import Aggregate, Field, FloatField, JSONField, Lookup
from django.db.models.expressions import Func


class JsonGroupArray(Aggregate):
    """Sqlite3 json_group_array() function."""

    allow_distinct = True
    function = "JSON_GROUP_ARRAY"
    name = "JsonGroupArray"
    output_field = JSONField()  # type: ignore


# TODO should only be fts5 fields
@Field.register_lookup
class FTS5Match(Lookup):
    """Sqlite3 FTS5 MATCH lookup."""

    lookup_name = "match"

    def as_sql(self, compiler, connection):
        """Generate MATCH sql."""
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        sql = f"{lhs} MATCH {rhs}"
        return sql, params


class ComicFTSRank(Func):
    """Sqlite3 FTS5 inverse rank lookup."""

    function = "rank"
    template = '("codex_comicfts"."rank" * -1)'
    output_field = FloatField()  # type: ignore

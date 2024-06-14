"""Custom Django DB functions."""

from django.db.models import Aggregate, JSONField


class JsonGroupArray(Aggregate):
    """Sqlite3 json_group_array() function."""

    allow_distinct = True
    function = "JSON_GROUP_ARRAY"
    name = "JsonGroupArray"
    output_field = JSONField()  # type: ignore

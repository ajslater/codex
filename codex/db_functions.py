"""Custom Django DB functions."""

from django.db.models import Aggregate, JSONField


class JsonGroupArray(Aggregate):
    """Sqlite3 json_group_array() function."""

    allow_distinct = True
    function = "JSON_GROUP_ARRAY"
    template = "%(function)s(%(distinct)s%(expressions)s)"

    def __init__(self, output_field=None, **kwargs):
        """Set output_field to JSONField."""
        if output_field is None:
            output_field = JSONField()
        super().__init__(output_field=output_field, **kwargs)

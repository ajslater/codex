"""Custom Django DB functions."""

from django.db.models import JSONField
from django.db.models.aggregates import Aggregate
from django.db.models.sql.query import Query


class JsonGroupArray(Aggregate):
    """Sqlite3 json_group_array() function."""

    allow_distinct = True
    function = 'JSON_GROUP_ARRAY'
    output_field = JSONField()
    template = '%(function)s(%(distinct)s%(expressions)s)'

class GroupByQuery(Query):

    def set_group_by(self, group_by=None):
        if group_by:
            self.group_by = group_by

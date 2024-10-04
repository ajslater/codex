"""Custom Compiler to force group_by."""
# If any group_by() is attached to the QuerySet, it completely overrides the compiler computed group_by

from django.db import connections
from django.db.models import Manager
from django.db.models.query import QuerySet
from django.db.models.sql.compiler import SQLCompiler
from django.db.models.sql.query import Query


class GroupBySQLCompiler(SQLCompiler):
    """Custom Compiler to force group_by."""

    def __init__(self, *args, **kwargs):
        """Initialize force group_by fields."""
        super().__init__(*args, **kwargs)
        self.force_group_by_table = ""
        self.force_group_by_fields = ()

    def set_force_group_by(self, table, fields):
        """Set the force group_by variables."""
        self.force_group_by_table = table
        self.force_group_by_fields = fields

    def get_group_by(self, *args, **kwargs):
        """If force group_by set, force it."""
        if self.force_group_by_table and self.force_group_by_fields:
            table = self.force_group_by_table
            group_by = []
            for field in self.force_group_by_fields:
                field_str = f'"{table}"."{field}"'
                entry = (field_str, ())
                group_by.append(entry)
        else:
            group_by = super().get_group_by(*args, **kwargs)
        return group_by


class GroupByQuery(Query):
    """Custom Query to use GroupBy Compiler."""

    def __init__(self, *args, **kwargs):
        """Init force group_by fields."""
        super().__init__(*args, **kwargs)
        self.force_group_by_table = ""
        self.force_group_by_fields = ()

    def get_compiler(self, using=None, connection=None, elide_empty=True):
        """Use the custom compiler instead of SQLCompiler."""
        if self.compiler == "SQLCompiler":
            if using is None and connection is None:
                reason = "Need either using or connection"
                raise ValueError(reason)
            if using:
                connection = connections[using]
            compiler = GroupBySQLCompiler(self, connection, using, elide_empty)
            compiler.set_force_group_by(
                self.force_group_by_table, self.force_group_by_fields
            )
        else:
            # Normal super() operation.
            compiler = super().get_compiler(using, connection, elide_empty)  # type: ignore

        return compiler

    def set_force_group_by(self, fields, model=None):
        """Set the force group_by fields."""
        if not model:
            model = self.model
        table = model._meta.db_table if model else ""
        self.force_group_by_table = table
        self.force_group_by_fields = fields


class GroupByQuerySet(QuerySet):
    """Custom Queryset that uses Custom compiler."""

    def __init__(self, model=None, query=None, using=None, hints=None):
        """Use the custom query with the custom compiler."""
        query = query or GroupByQuery(model)
        super().__init__(model=model, query=query, using=using, hints=hints)

    def group_by(self, *fields, model=None):
        """Force group_by operator."""
        obj = self._chain()  # type: ignore
        obj.query.set_force_group_by(fields, model=model)
        return obj

    def demote_joins(self, tables):
        """Force INNER JOINS."""
        obj = self._chain()  # type: ignore
        obj.query.demote_joins(tables)
        return obj


class GroupByManager(Manager.from_queryset(GroupByQuerySet)):
    """Use GroupBy QuerySet."""

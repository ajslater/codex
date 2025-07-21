"""Query the missing foreign keys methods."""

from django.db.models import Q

from codex.librarian.scribe.importer.const import DictModelType
from codex.librarian.scribe.importer.query.covers import QueryCustomCoversImporter
from codex.models.base import BaseModel
from codex.models.groups import BrowserGroupModel


class QueryForeignKeysFilterImporter(QueryCustomCoversImporter):
    """Query the missing foreign keys methods."""

    @staticmethod
    def _get_query_missing_simple_filter(
        key_rels: tuple[str, ...],
        key_values: tuple[str, ...],
    ):
        filter_args = {}
        rel = key_rels[0]
        values = frozenset(key[0] for key in key_values if key[0])
        filter_args[f"{rel}__in"] = values
        return Q(**filter_args)

    @staticmethod
    def _query_missing_complex_model_filter(
        key_rels: tuple[str, ...],
        key_values: tuple[tuple[str | None, ...], ...],
    ):
        """Add value filter to query filter map."""
        query_filter = Q()
        for keys in key_values:
            filter_dict = {}
            for rel, value in zip(key_rels, keys, strict=False):
                # for credit
                val = value[0] if isinstance(value, tuple) else value
                if val is None:
                    final_rel = rel + "__isnull"
                    val = True
                else:
                    final_rel = rel
                filter_dict[final_rel] = val
            query_filter |= Q(**filter_dict)
        return query_filter

    def query_missing_model_filter(
        self,
        model: type[BaseModel],
        key_rels: tuple[str, ...],
        key_value_tuples: tuple,
    ):
        """Get filters for the model."""
        if issubclass(model, DictModelType | BrowserGroupModel):
            fk_filter = self._query_missing_complex_model_filter(
                key_rels, key_value_tuples
            )
        else:
            fk_filter = self._get_query_missing_simple_filter(
                key_rels, key_value_tuples
            )
        return fk_filter

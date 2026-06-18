"""Query the missing foreign keys methods."""

from django.db.models.query_utils import Q

from codex.librarian.scribe.importer.const import (
    MODEL_SELECTOR_REL_MAP,
    DictModelType,
)
from codex.librarian.scribe.importer.query.covers import QueryCustomCoversImporter
from codex.models.base import BaseModel
from codex.models.collections import BrowserCollectionModel


class QueryForeignKeysFilterImporter(QueryCustomCoversImporter):
    """Query the missing foreign keys methods."""

    @staticmethod
    def _get_query_missing_simple_filter(
        key_rels: tuple[str, ...],
        key_values: tuple[str, ...],
    ) -> Q:
        filter_args = {}
        rel = key_rels[0]
        values = frozenset(key[0] for key in key_values if key[0])
        filter_args[f"{rel}__in"] = values
        return Q(**filter_args)

    @staticmethod
    def _query_missing_key_or_chain(
        key_rels: tuple[str, ...],
        key_values: tuple[tuple[str | None, ...], ...],
    ) -> Q:
        """Build the exact per-key AND/OR chain filter."""
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

    @classmethod
    def _query_missing_complex_model_filter(
        cls,
        model: type[BaseModel],
        key_rels: tuple[str, ...],
        key_values: tuple[tuple[str | None, ...], ...],
    ) -> Q:
        """
        Narrow with one indexed IN on the model's selector key rel.

        ``query_existing_mds`` matches exact key tuples in Python from
        the fetched values, so this filter only bounds the fetch — a
        superset row (same selector value under a different parent) is
        harmless. The per-key AND/OR chain this replaces cost one
        Django filter-resolution per leaf and a giant OR parse in
        SQLite per batch. Keys whose selector value is None (selector
        columns are non-null, so normally none) fall back to the
        chain.
        """
        selector_rel = MODEL_SELECTOR_REL_MAP.get(model)
        if not selector_rel or selector_rel not in key_rels:
            return cls._query_missing_key_or_chain(key_rels, key_values)
        index = key_rels.index(selector_rel)
        selector_values = set()
        residual_keys = []
        for keys in key_values:
            value = keys[index]
            # for credit (mirrors the chain's tuple unwrap)
            val = value[0] if isinstance(value, tuple) else value
            if val is None:
                residual_keys.append(keys)
            else:
                selector_values.add(val)
        query_filter = (
            Q(**{f"{selector_rel}__in": selector_values}) if selector_values else Q()
        )
        if residual_keys:
            query_filter |= cls._query_missing_key_or_chain(
                key_rels, tuple(residual_keys)
            )
        return query_filter

    def query_missing_model_filter(
        self,
        model: type[BaseModel],
        key_rels: tuple[str, ...],
        key_value_tuples: tuple,
    ) -> Q:
        """Get filters for the model."""
        if issubclass(model, DictModelType | BrowserCollectionModel):
            fk_filter = self._query_missing_complex_model_filter(
                model, key_rels, key_value_tuples
            )
        else:
            fk_filter = self._get_query_missing_simple_filter(
                key_rels, key_value_tuples
            )
        return fk_filter

"""Methods for querying missing dict models."""

from django.db.models import Q

from codex.librarian.importer.const import (
    DESIGNATION_FIELD_NAME,
    FK_CREATE,
    IDENTIFIER_URL_FIELD_NAME,
    QUERY_MODELS,
    DictModelType,
)
from codex.librarian.importer.query_fks.const import COMPLEX_M2M_MODEL_REL_MAP
from codex.librarian.importer.query_fks.groups import QueryForeignKeysGroupsImporter
from codex.models.named import Identifier, Universe

_UNQUERIED_FIELD_MODELS = frozenset({Identifier, Universe})
_UNQUERIED_FIELDS = frozenset({IDENTIFIER_URL_FIELD_NAME, DESIGNATION_FIELD_NAME})


class QueryForeignKeysComplexModelsImporter(QueryForeignKeysGroupsImporter):
    """Methods for querying missing dict models."""

    def _query_missing_complex_model_add_to_query_filter_map(
        self,
        query_model: DictModelType,
        dict_values: tuple,
        possible_create_objs: set[tuple],
        unqueried_field_restore_map: dict,
    ):
        """Add value filter to query filter map."""
        query_rels = COMPLEX_M2M_MODEL_REL_MAP[query_model]
        filter_dict = {}
        for rel, value in zip(query_rels, dict_values, strict=False):
            if rel in _UNQUERIED_FIELDS:
                if query_model not in unqueried_field_restore_map:
                    unqueried_field_restore_map[query_model] = {}
                if rel == IDENTIFIER_URL_FIELD_NAME:
                    key = dict_values[0:1]
                else:  # DESIGNATION_FIELD_NAME
                    key = dict_values[0]
                unqueried_field_restore_map[query_model][key] = value
            elif value is None:
                filter_dict[f"{rel}__isnull"] = True
            else:
                filter_dict[rel] = value
        possible_create_objs.add(dict_values)
        return Q(**filter_dict)

    @staticmethod
    def _query_missing_complex_model_identifiers_restore_unqueried_field(
        query_model: DictModelType,
        possible_create_objs: set[tuple],
        unqueried_field_restore_map: dict,
    ):
        """Restore urls to only the identifier create objs."""
        if query_model not in _UNQUERIED_FIELD_MODELS:
            return possible_create_objs
        restored_create_objs = set()
        for create_obj in possible_create_objs:
            value = unqueried_field_restore_map.get(query_model, {}).get(create_obj)
            restored_create_objs.add((*create_obj, value))
        return frozenset(restored_create_objs)

    def query_missing_complex_model(self, query_model: DictModelType, status):
        """Find missing dict type m2m models."""
        possible_objs = self.metadata[QUERY_MODELS].pop(query_model, None)
        if not possible_objs:
            return 0

        # Create possible_create_objs & a query filter map and cache the urls for
        # identifiers to be created, but not queried against
        possible_create_objs = set()
        query_filter = Q()
        unqeueried_field_restore_map = {}
        for values in possible_objs:
            query_filter |= self._query_missing_complex_model_add_to_query_filter_map(
                query_model,
                values,
                possible_create_objs,
                unqeueried_field_restore_map,
            )

        # Finally run the query and get only the correct create_objs
        self.query_create_metadata(
            query_model,
            possible_create_objs,
            None,
            query_filter,
            status,
        )

        possible_create_objs = (
            self._query_missing_complex_model_identifiers_restore_unqueried_field(
                query_model, possible_create_objs, unqeueried_field_restore_map
            )
        )

        # Final Cleanup
        if query_model not in self.metadata[FK_CREATE]:
            self.metadata[FK_CREATE][query_model] = set()
        self.metadata[FK_CREATE][query_model] |= possible_create_objs
        count = len(self.metadata[FK_CREATE][query_model])
        if count:
            vnp = query_model._meta.verbose_name_plural
            vnp = vnp.title() if vnp else query_model._meta.verbose_name
            self.log.info(f"Prepared {count} new {vnp}.")
        status.add_complete(count)
        self.status_controller.update(status)
        return count

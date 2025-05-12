"""Methods for querying missing dict models."""

from django.db.models import Q

from codex.librarian.importer.const import (
    FK_CREATE,
    IDENTIFIER_URL_FIELD_NAME,
    QUERY_MODELS,
    DictModelType,
)
from codex.librarian.importer.query_fks.const import DICT_MODEL_REL_MAP
from codex.librarian.importer.query_fks.groups import QueryForeignKeysGroupsImporter
from codex.models.named import Identifier


class QueryForeignKeysDictModelsImporter(QueryForeignKeysGroupsImporter):
    """Methods for querying missing dict models."""

    def _query_missing_dict_model_add_to_query_filter_map(
        self,
        query_model: DictModelType,
        dict_values: tuple,
        possible_create_objs: set[tuple],
        url_restore_map: dict,
    ):
        """Add value filter to query filter map."""
        query_rels = DICT_MODEL_REL_MAP[query_model]
        filter_dict = {}
        for rel, value in zip(query_rels, dict_values, strict=True):
            if rel == IDENTIFIER_URL_FIELD_NAME:
                url_restore_map[dict_values[0:1]] = value
            elif value is None:
                filter_dict[f"{rel}__isnull"] = True
            else:
                filter_dict[rel] = value

        possible_create_objs.add(dict_values)
        return Q(**filter_dict)

    @staticmethod
    def _query_missing_dict_model_identifiers_restore_urls(
        query_model: DictModelType,
        possible_create_objs: set[tuple],
        url_restore_map: dict,
    ):
        """Restore urls to only the identifier create objs."""
        if query_model != Identifier:
            return possible_create_objs
        restored_create_objs = []
        for create_obj in possible_create_objs:
            url = url_restore_map.get(create_obj)
            restored_create_objs.append((*create_obj, url))
        return restored_create_objs

    def _query_missing_dict_model(
        self, query_model: DictModelType, create_objs_key: str, status
    ):
        """Find missing dict type m2m models."""
        possible_objs = self.metadata[QUERY_MODELS].pop(query_model, None)
        if not possible_objs:
            return 0

        # Create possible_create_objs & a query filter map and cache the urls for
        # identifiers to be created, but not queried against
        possible_create_objs = set()
        query_filter = Q()
        url_restore_map = {}
        for values in possible_objs:
            query_filter |= self._query_missing_dict_model_add_to_query_filter_map(
                query_model,
                values,
                possible_create_objs,
                url_restore_map,
            )

        # Finally run the query and get only the correct create_objs
        self.query_create_metadata(
            query_model,
            possible_create_objs,
            None,
            query_filter,
            status,
        )

        possible_create_objs = self._query_missing_dict_model_identifiers_restore_urls(
            query_model, possible_create_objs, url_restore_map
        )

        # Final Cleanup
        self.metadata[FK_CREATE][create_objs_key].update(possible_create_objs)
        count = len(self.metadata[FK_CREATE][create_objs_key])
        if count:
            vnp = query_model._meta.verbose_name_plural
            vnp = vnp.title() if vnp else "Nothings"
            self.log.info(f"Prepared {count} new {vnp}.")
        status.add_complete(count)
        self.status_controller.update(status, notify=False)
        return count

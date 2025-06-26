"""Query the missing foreign keys methods."""

from django.db.models import Q

from codex.librarian.scribe.importer.const import (
    CREATE_FKS,
    MODEL_REL_MAP,
    QUERY_MODELS,
    TOTAL,
    UPDATE_FKS,
    get_key_index,
)
from codex.librarian.scribe.importer.query.update_fks import QueryIsUpdateImporter
from codex.librarian.scribe.importer.status import ImporterStatusTypes
from codex.librarian.status import Status
from codex.models.base import BaseModel
from codex.settings import FILTER_BATCH_SIZE
from codex.util import flatten


class QueryForeignKeysQueryImporter(QueryIsUpdateImporter):
    """Query the missing foreign keys methods."""

    @staticmethod
    def query_existing_mds(model: type[BaseModel], fk_filter: Q):
        """Query existing metatata tables."""
        rels = MODEL_REL_MAP[model]
        fields = tuple(filter(bool, flatten(rels)))
        qs = model.objects.filter(fk_filter).distinct().values_list(*fields)
        extra_index = get_key_index(model)
        return {
            existing_values[:extra_index]: existing_values for existing_values in qs
        }

    def _query_missing_models_batch(  # noqa: PLR0913
        self,
        model: type[BaseModel],
        start: int,
        all_proposed_key_values: tuple,
        proposed_values_map: dict[tuple, set[tuple]],
        create_values: set[tuple],
        update_values: set[tuple],
        status,
    ):
        # Do this in batches so as not to exceed the 1k line sqlite limit
        end = start + FILTER_BATCH_SIZE
        batch_proposed_key_tuples = all_proposed_key_values[start:end]
        num_in_batch = len(batch_proposed_key_tuples)

        # Existing
        key_rels = MODEL_REL_MAP[model][0]
        fk_filter = self.query_missing_model_filter(
            model,
            key_rels,
            batch_proposed_key_tuples,
        )
        existing_values_map = self.query_existing_mds(model, fk_filter)

        for key_values in batch_proposed_key_tuples:
            proposed_values_set = proposed_values_map.pop(key_values)
            existing_values = existing_values_map.pop(key_values, None)

            do_update, best_values = self.query_model_best_values(
                model, key_values, existing_values, proposed_values_set
            )
            if existing_values:
                if do_update:
                    update_values.add(best_values)
            else:
                create_values.add(best_values)

        status.add_complete(num_in_batch)
        self.status_controller.update(status)

    def _finish_query_missing(
        self,
        model: type[BaseModel],
        values: set | frozenset,
        key: str,
        title: str,
    ):
        if values:
            fks = self.metadata[key]
            if model not in fks:
                fks[model] = set()
            fks[model] |= values
            level = "INFO"
        else:
            level = "DEBUG"
        num = len(values)
        verb = "create" if key == CREATE_FKS else "update"
        self.log.log(level, f"Prepared {num} {title} for {verb}.")

    def query_missing_models(
        self,
        model: type[BaseModel],
        all_proposed_values: set,
        status,
    ):
        """Find missing foreign key models."""
        if not all_proposed_values:
            return 0
        proposed_extra_index = get_key_index(model)
        proposed_values_map = {}
        for values_tuple in all_proposed_values:
            key_proposed_values = values_tuple[:proposed_extra_index]
            if not key_proposed_values:
                continue
            if key_proposed_values not in proposed_values_map:
                proposed_values_map[key_proposed_values] = set()
            proposed_values_map[key_proposed_values].add(values_tuple)
        num_all_proposed_values = len(all_proposed_values)
        proposed_key_values = tuple(proposed_values_map.keys())
        start = 0

        vnp = model._meta.verbose_name_plural
        title = vnp.title() if vnp else ""
        status.subtitle = title

        create_values = set()
        update_values = set()

        while start < num_all_proposed_values:
            self._query_missing_models_batch(
                model,
                start,
                proposed_key_values,
                proposed_values_map,
                create_values,
                update_values,
                status,
            )
            start += FILTER_BATCH_SIZE

        self._finish_query_missing(model, create_values, CREATE_FKS, title)
        self._finish_query_missing(model, update_values, UPDATE_FKS, title)
        status.subtitle = ""
        return num_all_proposed_values

    def _query_missing_model(self, model: type[BaseModel], status):
        """Find missing model and update create and update sets."""
        count = 0
        proposed_values = self.metadata[QUERY_MODELS].pop(model, None)
        if not proposed_values:
            return count

        # Finally run the query and get only the correct create_objs
        return self.query_missing_models(
            model,
            proposed_values,
            status,
        )

    def _set_fk_totals(self, fk_key: str, status_type: ImporterStatusTypes):
        total_fks = 0
        fks = self.metadata[fk_key]
        for rows in fks.values():
            total_fks += len(rows)
        status = Status(status_type, None, total_fks)
        self.status_controller.update(status, notify=False)
        self.metadata[fk_key][TOTAL] = total_fks

    def query_all_missing_models(self):
        """Find all missing foreign key models."""
        num_models = self.sum_ops(QUERY_MODELS)
        status = Status(ImporterStatusTypes.QUERY_MISSING_TAGS, 0, num_models)
        try:
            if not num_models:
                return
            self.status_controller.start(status)
            for model in tuple(self.metadata[QUERY_MODELS].keys()):
                if self.abort_event.is_set():
                    return
                self._query_missing_model(model, status)
            self.metadata.pop(QUERY_MODELS)
            self._set_fk_totals(CREATE_FKS, ImporterStatusTypes.CREATE_TAGS)
            self._set_fk_totals(UPDATE_FKS, ImporterStatusTypes.UPDATE_TAGS)
        finally:
            self.status_controller.finish(status)

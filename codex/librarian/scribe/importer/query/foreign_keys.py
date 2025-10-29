"""Query the missing foreign keys methods."""

from codex.librarian.scribe.importer.const import (
    CREATE_FKS,
    FK_KEYS,
    MODEL_REL_MAP,
    MODEL_SELECT_RELATED,
    QUERY_MODELS,
    TOTAL,
    UPDATE_FKS,
    get_key_index,
)
from codex.librarian.scribe.importer.query.update_fks import QueryIsUpdateImporter
from codex.librarian.scribe.importer.statii.create import (
    ImporterCreateTagsStatus,
    ImporterUpdateTagsStatus,
)
from codex.librarian.scribe.importer.statii.query import ImporterQueryMissingTagsStatus
from codex.librarian.status import Status
from codex.models.base import BaseModel
from codex.models.named import Universe
from codex.settings import FILTER_BATCH_SIZE
from codex.util import flatten


class QueryForeignKeysQueryImporter(QueryIsUpdateImporter):
    """Query the missing foreign keys methods."""

    def query_existing_mds(self, model: type[BaseModel], batch_proposed_key_tuples):
        """Query existing metadata tables."""
        key_rels: tuple[str, ...] = MODEL_REL_MAP[model][0]  # pyright:ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
        fk_filter = self.query_missing_model_filter(
            model,
            key_rels,
            batch_proposed_key_tuples,
        )
        rels = MODEL_REL_MAP[model]
        select_related = MODEL_SELECT_RELATED.get(model, ())
        fields = tuple(filter(bool, flatten(rels)))
        qs = model.objects
        qs = qs.select_related(*select_related)
        qs = qs.filter(fk_filter).distinct().values_list(*fields)
        extra_index = get_key_index(model)
        has_id = bool(rels[1])
        existing_mds = {}
        for existing_values in qs:
            key = existing_values[:extra_index]
            value = existing_values[extra_index:]
            if has_id:
                identifier = value[:3] if any(value[:3]) else None
                value = (identifier, *value[3:])
            existing_mds[key] = value
        return existing_mds

    def _query_missing_models_batch(
        self,
        model: type[BaseModel],
        start: int,
        all_proposed_key_values: tuple,
        proposed_values_map: dict[tuple, set[tuple]],
        create_values: set[tuple],
        update_values: set[tuple],
        fts_values: dict[tuple, tuple],
        status: Status,
    ):
        # Do this in batches so as not to exceed the 1k sqlite query depth limit
        end = start + FILTER_BATCH_SIZE
        batch_proposed_key_tuples = all_proposed_key_values[start:end]
        num_in_batch = len(batch_proposed_key_tuples)

        existing_values_map = self.query_existing_mds(model, batch_proposed_key_tuples)

        for key_values in batch_proposed_key_tuples:
            proposed_extra_values_set = proposed_values_map.pop(key_values)
            exists = key_values in existing_values_map
            existing_extra_values = existing_values_map.pop(key_values, None)

            do_update, best_extra_values = self.query_model_best_extra_values(
                model, existing_extra_values, proposed_extra_values_set
            )
            best_values = (*key_values, *best_extra_values)
            if exists:
                if do_update:
                    update_values.add(best_values)
            else:
                create_values.add(best_values)
            if model is Universe:
                fts_values[key_values] = best_extra_values

        status.increment_complete(num_in_batch)
        self.status_controller.update(status)

    def _finish_query_missing(
        self,
        model: type[BaseModel],
        values: set | frozenset | dict,
        key: str,
        title: str,
    ):
        if values:
            fks = self.metadata[key]
            if isinstance(values, dict):
                if model not in fks:
                    fks[model] = {}
                fks[model].update(values)
            else:
                if model not in fks:
                    fks[model] = set()
                fks[model] |= values
            level = "INFO"
        else:
            level = "DEBUG"
        num = len(values)
        match key:
            case FK_KEYS.CREATE_FKS:
                verb = "create"
            case FK_KEYS.UPDATE_FKS:
                verb = "update"
            case _:
                verb = ""
        if verb:
            self.log.log(level, f"Prepared {num} {title} for {verb}.")

    def query_missing_models(
        self,
        model: type[BaseModel],
        proposed_values_map: dict[tuple, set[tuple]],
        status: Status,
    ):
        """Find missing foreign key models."""
        if not proposed_values_map:
            return 0
        num_all_proposed_values = len(proposed_values_map)
        proposed_key_values = tuple(proposed_values_map.keys())
        start = 0

        vnp = model._meta.verbose_name_plural
        title = vnp.title() if vnp else ""
        status.subtitle = title

        create_values = set()
        update_values = set()
        fts_values = {}

        while start < num_all_proposed_values:
            self._query_missing_models_batch(
                model,
                start,
                proposed_key_values,
                proposed_values_map,
                create_values,
                update_values,
                fts_values,
                status,
            )
            start += FILTER_BATCH_SIZE

        self._finish_query_missing(model, create_values, CREATE_FKS, title)
        self._finish_query_missing(model, update_values, UPDATE_FKS, title)
        status.subtitle = ""
        return num_all_proposed_values

    def _query_missing_model(self, model: type[BaseModel], status: Status):
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

    def _set_fk_totals(self, fk_key: str, status_class):
        total_fks = 0
        fks = self.metadata[fk_key]
        for rows in fks.values():
            total_fks += len(rows)
        status = status_class(None, total_fks)
        self.status_controller.update(status, notify=False)
        self.metadata[fk_key][TOTAL] = total_fks

    def query_all_missing_models(self):
        """Find all missing foreign key models."""
        num_models = self.sum_ops(QUERY_MODELS)
        status = ImporterQueryMissingTagsStatus(0, num_models)
        try:
            if not num_models:
                return num_models
            self.status_controller.start(status)
            for model in tuple(self.metadata[QUERY_MODELS].keys()):
                if self.abort_event.is_set():
                    return num_models
                self._query_missing_model(model, status)
            self.metadata.pop(QUERY_MODELS)
            self._set_fk_totals(CREATE_FKS, ImporterCreateTagsStatus)
            self._set_fk_totals(UPDATE_FKS, ImporterUpdateTagsStatus)
        finally:
            self.status_controller.finish(status)
        return status.complete

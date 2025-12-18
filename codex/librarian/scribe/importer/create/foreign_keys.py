"""
Create all missing comic many to many objects for an import.

So we may safely create the comics next.
"""

from collections.abc import Mapping
from itertools import chain

from codex.librarian.scribe.importer.const import (
    COMPLEX_M2M_MODELS,
    CREATE_FKS,
    FTS_CREATED_M2MS,
    FTS_UPDATED_M2MS,
    GROUP_MODEL_COUNT_FIELDS,
    MODEL_REL_MAP,
    TOTAL,
    UPDATE_FKS,
)
from codex.librarian.scribe.importer.create.const import (
    CUSTOM_COVER_MODELS,
    DEFAULT_NON_NULL_CHARFIELD_NAMES,
    GROUP_BASE_FIELDS,
    GROUP_BASE_MODELS,
    MODEL_CREATE_ARGS_MAP,
    NON_NULL_CHARFIELD_NAMES,
    ORDERED_CREATE_MODELS,
)
from codex.librarian.scribe.importer.create.folders import (
    CreateForeignKeysFolderImporter,
)
from codex.librarian.scribe.importer.statii.create import (
    ImporterCreateTagsStatus,
    ImporterUpdateTagsStatus,
)
from codex.librarian.status import Status
from codex.models.base import BaseModel
from codex.models.groups import Folder
from codex.models.named import Universe


class CreateForeignKeysCreateUpdateImporter(CreateForeignKeysFolderImporter):
    """Methods for creating foreign keys."""

    @staticmethod
    def _get_create_update_args(
        model: type[BaseModel],
        key_args_map: Mapping,
        update_args_map: Mapping,
        values_tuple: tuple,
    ):
        """Create key args and update args."""
        key_args = {}
        update_args = {}
        num_keys = len(key_args_map)
        for index, (field_name, field_model) in enumerate(
            chain(key_args_map.items(), update_args_map.items())
        ):
            value = values_tuple[index]
            if field_model and value is not None:
                key_rels = MODEL_REL_MAP[field_model][0]
                if field_model in GROUP_MODEL_COUNT_FIELDS and index < num_keys:
                    value = values_tuple[: index + 1]
                elif not isinstance(value, tuple):
                    value = (value,)
                sub_model_key_args = dict(zip(key_rels, value, strict=True))
                value = field_model.objects.get(**sub_model_key_args)
            non_null_charfield_names = NON_NULL_CHARFIELD_NAMES.get(
                model, DEFAULT_NON_NULL_CHARFIELD_NAMES
            )
            if value is None and field_name in non_null_charfield_names:
                value = ""
            arg_map = key_args if index < num_keys else update_args
            arg_map[field_name] = value
        return key_args, update_args

    def _add_custom_cover(self, model, obj):
        self.add_custom_cover_to_group(model, obj)

    def _finish_create_update(self, model, objs, status: Status):
        count = len(objs)
        if count:
            vnp = model._meta.verbose_name_plural
            title = vnp.title() if vnp else model._meta.verbose_name
            self.log.info(f"Created {count} {title}.")
        status.increment_complete(count)
        self.status_controller.update(status)

    def _bulk_create_models(
        self,
        model: type[BaseModel],
        status,
    ):
        """Bulk create a dict type m2m model."""
        count = 0
        create_tuples = self.metadata[CREATE_FKS].pop(model, None)
        if not create_tuples:
            return count
        status.subtitle = model._meta.verbose_name_plural
        self.status_controller.update(status)
        key_args_map, update_args_map = MODEL_CREATE_ARGS_MAP[model]
        create_objs = []
        create_tuples = sorted(create_tuples, key=str)
        created_fts_values = {}
        for values_tuple in create_tuples:
            key_args, update_args = self._get_create_update_args(
                model,
                key_args_map,
                update_args_map,
                values_tuple,  # ty: ignore[invalid-argument-type]
            )
            obj = model(**key_args, **update_args)
            obj.presave()
            if model in CUSTOM_COVER_MODELS:
                self._add_custom_cover(model, obj)
            create_objs.append(obj)
            if model == Universe and update_args:
                fts_update_values = tuple(
                    value for value in update_args.values() if isinstance(value, str)
                )
                created_fts_values[tuple(key_args.values())] = fts_update_values

        if created_fts_values:
            field_name = model.__name__.lower() + "s"
            self.metadata[FTS_CREATED_M2MS][field_name] = created_fts_values

        update_fields = tuple(key_args_map.keys()) + tuple(update_args_map.keys())
        if model in GROUP_BASE_MODELS:
            update_fields += GROUP_BASE_FIELDS

        count = len(create_objs)
        model.objects.bulk_create(
            create_objs,
            update_conflicts=True,
            update_fields=update_fields,
            unique_fields=model._meta.unique_together[0],
        )
        self._finish_create_update(model, create_objs, status)
        return count

    def bulk_create_all_models(self, status):
        """
        Bulk create all dict type m2m models.

        Done in three phases for dependency order
        """
        count = 0
        complex_models = []
        # These come first in this order
        for model in ORDERED_CREATE_MODELS:
            count += self._bulk_create_models(
                model,
                status,
            )
        for model in tuple(self.metadata[CREATE_FKS]):
            if model in COMPLEX_M2M_MODELS:
                # These must come last
                complex_models.append(model)
            else:
                count += self._bulk_create_models(
                    model,
                    status,
                )
        for model in complex_models:
            count += self._bulk_create_models(
                model,
                status,
            )
        return count

    def _bulk_update_models(self, model: type[BaseModel], status):
        count = 0
        update_tuples = self.metadata[UPDATE_FKS].pop(model, None)
        if not update_tuples:
            return count
        status.subtitle = model._meta.verbose_name_plural
        self.status_controller.update(status)
        key_args_map, update_args_map = MODEL_CREATE_ARGS_MAP[model]
        update_objs = []
        update_tuples = sorted(update_tuples, key=str)
        fts_update_pks = set()
        for values_tuple in update_tuples:
            key_args, update_args = self._get_create_update_args(
                model,
                key_args_map,
                update_args_map,
                values_tuple,  # ty: ignore[invalid-argument-type]
            )
            obj = model.objects.get(**key_args)
            for key, value in update_args.items():
                setattr(obj, key, value)
            obj.presave()
            if model in CUSTOM_COVER_MODELS:
                self._add_custom_cover(model, obj)
            update_objs.append(obj)
            # Generic code, but really it's only universe
            # if tuple(
            #    value for value in update_args.values() if isinstance(value, str)
            # ):
            if model == Universe:
                fts_update_pks.add(obj.pk)

        if fts_update_pks:
            field_name = model.__name__.lower() + "s"
            self.metadata[FTS_UPDATED_M2MS][field_name] = fts_update_pks

        update_fields = tuple(update_args_map.keys())
        if model in GROUP_BASE_MODELS:
            update_fields += GROUP_BASE_FIELDS

        count = len(update_objs)
        model.objects.bulk_update(update_objs, fields=update_fields)
        self._finish_create_update(model, update_objs, status)
        return count

    def bulk_update_all_models(self, status):
        """Bulk update all complex models."""
        count = 0
        for model in tuple(self.metadata[UPDATE_FKS].keys()):
            count += self._bulk_update_models(model, status)
        return count

    def create_all_fks(self) -> int:
        """Bulk create all foreign keys."""
        count = 0
        fkc = self.metadata.get(CREATE_FKS, {})
        create_status = ImporterCreateTagsStatus(0, fkc.pop(TOTAL, 0))
        try:
            self.metadata[FTS_CREATED_M2MS] = {}
            if not fkc:
                return count
            self.status_controller.start(create_status)
            count += self.bulk_folders_create(
                fkc.pop(Folder, frozenset()), create_status
            )
            count += self.bulk_create_all_models(create_status)
        finally:
            self.metadata.pop(CREATE_FKS, None)
            self.status_controller.finish(create_status)
        return count

    def update_all_fks(self) -> int:
        """Bulk update all foreign keys."""
        count = 0
        fku = self.metadata.get(UPDATE_FKS, {})
        update_status = ImporterUpdateTagsStatus(0, fku.pop(TOTAL, 0))
        try:
            self.metadata[FTS_UPDATED_M2MS] = {}
            if not fku:
                return count
            self.status_controller.start(update_status)
            count += self.bulk_folders_update(
                fku.pop(Folder, frozenset()), update_status
            )
            count += self.bulk_update_all_models(update_status)
        finally:
            self.metadata.pop(UPDATE_FKS, None)
            self.status_controller.finish(update_status)
        return count

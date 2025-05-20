"""
Create all missing comic foreign keys for an import.

So we may safely create the comics next.
"""

from icecream import ic

from codex.librarian.importer.const import (
    FK_CREATE,
    FKC_CREATE_FKS,
    FKC_CREATE_GROUPS,
    FKC_FOLDER_PATHS,
    FKC_TOTAL_FKS,
    FKC_UPDATE_GROUPS,
    DictModelType,
)
from codex.librarian.importer.create_fks.const import (
    CREATE_DICT_FUNCTION_ARGS,
    CREATE_DICT_UPDATE_FIELDS,
    GROUP_BASE_FIELDS,
    NAMED_MODEL_UPDATE_FIELDS,
)
from codex.librarian.importer.create_fks.folders import (
    CreateForeignKeysFolderImporter,
)
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.status import Status
from codex.models import StoryArc
from codex.models.named import NamedModel


class CreateForeignKeysImporter(CreateForeignKeysFolderImporter):
    """Methods for creating foreign keys."""

    def _bulk_create_named_models(self, named_class: type[NamedModel], names, status):
        """Bulk create named models."""
        count = len(names)
        if not count:
            return
        create_named_objs = []
        is_story_arc = named_class == StoryArc
        for name in names:
            named_obj = named_class(name=name)
            if is_story_arc:
                named_obj.presave()
                self._add_custom_cover_to_group(StoryArc, named_obj)
            create_named_objs.append(named_obj)

        update_fields = NAMED_MODEL_UPDATE_FIELDS
        if is_story_arc:
            update_fields += GROUP_BASE_FIELDS

        ic("CREATE", named_class, names)
        named_class.objects.bulk_create(
            create_named_objs,
            update_conflicts=True,
            update_fields=update_fields,
            unique_fields=named_class._meta.unique_together[0],
        )
        if count:
            vnp = named_class._meta.verbose_name_plural
            title = vnp.title() if vnp else named_class._meta.verbose_name
            self.log.info(f"Created {count} {title}.")
        status.add_complete(count)
        self.status_controller.update(status)

    def _bulk_create_dict_models(
        self,
        create_args_dict: dict,
        model: DictModelType,
        status,
    ):
        """Bulk create a dict type m2m model."""
        create_tuples = self.metadata[FK_CREATE].pop(model, None)
        if not create_tuples:
            return
        ic("CREATE", model, create_args_dict, create_tuples)
        create_objs = []
        for values_tuple in create_tuples:
            args = {}
            for index, (key, field_model) in enumerate(create_args_dict.items()):
                if field_model is None:
                    args[key] = values_tuple[index]
                else:
                    args[key] = (
                        field_model.objects.get(name=values_tuple[index])
                        if values_tuple[index]
                        else None
                    )

            obj = model(**args)
            create_objs.append(obj)
        ic(model, create_objs)

        model.objects.bulk_create(
            create_objs,
            update_conflicts=True,
            update_fields=CREATE_DICT_UPDATE_FIELDS[model],
            unique_fields=model._meta.unique_together[0],
        )
        count = len(create_objs)
        if count:
            vnp = model._meta.verbose_name_plural
            title = vnp.title() if vnp else model._meta.verbose_name
            self.log.info(f"Created {count} {title}.")
        status.add_complete(count)
        self.status_controller.update(status)

    def create_all_fks(self):
        """Bulk create all foreign keys."""
        fkc = self.metadata.get(FK_CREATE)
        if not fkc:
            return

        status = Status(ImportStatusTypes.CREATE_TAGS, 0, fkc.pop(FKC_TOTAL_FKS, None))
        try:
            self.status_controller.start(status)

            for group_class, group_tree_counts in fkc.pop(
                FKC_CREATE_GROUPS, {}
            ).items():
                self.bulk_group_create(group_tree_counts, group_class, status)

            for group_class, group_tree_counts in fkc.pop(
                FKC_UPDATE_GROUPS, {}
            ).items():
                self.bulk_group_updater(group_tree_counts, group_class, status)

            self.bulk_folders_create(fkc.pop(FKC_FOLDER_PATHS, frozenset()), status)

            ic(fkc[FKC_CREATE_FKS])
            for named_class, names in fkc.pop(FKC_CREATE_FKS, {}).items():
                self._bulk_create_named_models(named_class, names, status)

            # These all depend on bulk_create_named_models running first
            for model, create_args_dict in CREATE_DICT_FUNCTION_ARGS.items():
                self._bulk_create_dict_models(
                    create_args_dict,
                    model,
                    status,
                )

        finally:
            self.metadata.pop(FK_CREATE, None)
            self.status_controller.finish(status)
        self.changed += status.complete if status.complete else 0

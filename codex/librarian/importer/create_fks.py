"""Create all missing comic foreign keys for an import.

So we may safely create the comics next.
"""

from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist

from codex.librarian.importer.const import (
    BULK_UPDATE_FOLDER_FIELDS,
    CLASS_CUSTOM_COVER_GROUP_MAP,
    COUNT_FIELDS,
    CREATE_DICT_UPDATE_FIELDS,
    FK_CREATE,
    FKC_CONTRIBUTORS,
    FKC_CREATE_FKS,
    FKC_CREATE_GROUPS,
    FKC_FOLDER_PATHS,
    FKC_IDENTIFIERS,
    FKC_STORY_ARC_NUMBERS,
    FKC_TOTAL_FKS,
    FKC_UPDATE_GROUPS,
    GROUP_BASE_FIELDS,
    GROUP_UPDATE_FIELDS,
    IMPRINT,
    ISSUE_COUNT,
    NAMED_MODEL_UPDATE_FIELDS,
    PUBLISHER,
    SERIES,
    VOLUME_COUNT,
)
from codex.librarian.importer.create_covers import CreateCoversImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import (
    Contributor,
    ContributorPerson,
    ContributorRole,
    CustomCover,
    Folder,
    Imprint,
    Publisher,
    Series,
    StoryArc,
    StoryArcNumber,
    Volume,
)
from codex.models.named import Identifier, IdentifierType
from codex.status import Status


class CreateForeignKeysImporter(CreateCoversImporter):
    """Methods for creating foreign keys."""

    @staticmethod
    def _add_custom_cover_to_group(group_class, obj):
        """If a custom cover exists for this group, add it."""
        group = CLASS_CUSTOM_COVER_GROUP_MAP.get(group_class)
        if not group:
            # Normal, volume doesn't link to covers
            return
        try:
            cover = CustomCover.objects.filter(group=group, sort_name=obj.sort_name)[0]
            obj.custom_cover = cover
        except (IndexError, ObjectDoesNotExist):
            pass

    @classmethod
    def _create_group_obj(cls, group_class, group_param_tuple, group_count):
        """Create a set of browser group objects."""
        defaults = {"name": group_param_tuple[-1]}
        if group_class in (Imprint, Series, Volume):
            defaults[PUBLISHER] = Publisher.objects.get(name=group_param_tuple[0])
        if group_class in (Series, Volume):
            defaults[IMPRINT] = Imprint.objects.get(
                publisher=defaults[PUBLISHER],
                name=group_param_tuple[1],
            )

        if group_class is Series:
            defaults[VOLUME_COUNT] = group_count
        elif group_class is Volume:
            defaults[SERIES] = Series.objects.get(
                publisher=defaults[PUBLISHER],
                imprint=defaults[IMPRINT],
                name=group_param_tuple[2],
            )
            defaults[ISSUE_COUNT] = group_count

        obj = group_class(**defaults)
        obj.presave()
        cls._add_custom_cover_to_group(group_class, obj)
        return obj

    @staticmethod
    def _update_group_obj(group_class, group_param_tuple, group_count):
        """Update group counts for a Series or Volume."""
        if group_count is None:
            return None
        search_kwargs = {
            f"{PUBLISHER}__name": group_param_tuple[0],
            f"{IMPRINT}__name": group_param_tuple[1],
            "name": group_param_tuple[-1],
        }
        if group_class == Volume:
            search_kwargs[f"{SERIES}__name"] = group_param_tuple[2]

        obj = group_class.objects.get(**search_kwargs)
        count_field = COUNT_FIELDS[group_class]
        obj_count = getattr(obj, count_field)
        if obj_count is None or group_count > obj_count:
            setattr(obj, count_field, group_count)
        else:
            obj = None
        return obj

    def _bulk_group_create(self, group_tree_counts, group_class, status):
        """Bulk creates groups."""
        count = 0
        if not group_tree_counts:
            return
        create_groups = []
        for group_param_tuple, group_count in group_tree_counts.items():
            obj = self._create_group_obj(group_class, group_param_tuple, group_count)
            create_groups.append(obj)
        update_fields = GROUP_UPDATE_FIELDS[group_class]
        if group_class in CLASS_CUSTOM_COVER_GROUP_MAP:
            update_fields += ("custom_cover",)
        group_class.objects.bulk_create(
            create_groups,
            update_conflicts=True,
            update_fields=update_fields,
            unique_fields=group_class._meta.unique_together[0],
        )
        count += len(create_groups)
        if count:
            vnp = group_class._meta.verbose_name_plural.title()
            self.log.info(f"Created {count} {vnp}.")
        status.add_complete(count)
        self.status_controller.update(status)
        return

    def _bulk_group_updater(self, group_tree_counts, group_class, status):
        """Bulk update groups."""
        if not group_tree_counts:
            return
        update_groups = []
        for group_param_tuple, group_count in group_tree_counts.items():
            obj = self._update_group_obj(group_class, group_param_tuple, group_count)
            if obj:
                update_groups.append(obj)
        count_field = COUNT_FIELDS[group_class]
        group_class.objects.bulk_update(update_groups, fields=[count_field])
        count = len(update_groups)
        if count:
            vnp = group_class._meta.verbose_name_plural.title()
            self.log.info(f"Updated {count} {vnp}.")
        status.add_complete(count)
        self.status_controller.update(status)

    def _bulk_folders_create_add_folder(self, path, create_folders):
        """Add one folder to the create list."""
        parent_path = str(path.parent)
        parent = None
        try:
            parent = Folder.objects.get(path=parent_path)
        except Folder.DoesNotExist:
            if path.parent != Path(self.library.path):
                self.log.warning(
                    f"Can't find parent folder {parent_path}"
                    f" for {path} in library {self.library.path}"
                )
        folder = Folder(
            library=self.library,
            path=str(path),
            name=path.name,
            parent_folder=parent,
        )
        folder.presave()
        self._add_custom_cover_to_group(Folder, folder)
        create_folders.append(folder)

    def _bulk_folders_create_depth_level(self, paths, status):
        """Create a depth level of folders."""
        create_folders = []
        for path in sorted(paths):
            self._bulk_folders_create_add_folder(path, create_folders)
        Folder.objects.bulk_create(
            create_folders,
            update_conflicts=True,
            update_fields=BULK_UPDATE_FOLDER_FIELDS,
            unique_fields=Folder._meta.unique_together[0],  # type: ignore
        )
        count = len(create_folders)
        status.add_complete(count)
        self.status_controller.update(status)
        return count

    def bulk_folders_create(self, folder_paths: frozenset, status):
        """Create folders breadth first."""
        count = 0
        if not folder_paths:
            return
        # group folder paths by depth
        folder_path_dict = {}
        for path_str in folder_paths:
            path = Path(path_str)
            path_length = len(path.parts)
            if path_length not in folder_path_dict:
                folder_path_dict[path_length] = set()
            folder_path_dict[path_length].add(path)

        # create each depth level first to ensure we can assign parents
        for depth_level in sorted(folder_path_dict):
            paths = sorted(folder_path_dict[depth_level])
            level_count = self._bulk_folders_create_depth_level(paths, status)
            count += level_count
            self.log.debug(
                f"Created {level_count} Folders at depth level {depth_level}"
            )

        if count:
            self.log.info(f"Created {count} Folders.")
        self.status_controller.update(status)

    def _bulk_create_named_models(self, names, named_class, status):
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

        named_class.objects.bulk_create(
            create_named_objs,
            update_conflicts=True,
            update_fields=update_fields,
            unique_fields=named_class._meta.unique_together[0],
        )
        if count:
            vnp = named_class._meta.verbose_name_plural.title()
            self.log.info(f"Created {count} {vnp}.")
        status.add_complete(count)
        self.status_controller.update(status)

    @staticmethod
    def _create_contributor_args(values):
        return {
            "role": ContributorRole.objects.get(name=values[0]) if values[0] else None,
            "person": ContributorPerson.objects.get(name=values[1]),
        }

    @staticmethod
    def _create_story_arc_number_args(values):
        return {"story_arc": StoryArc.objects.get(name=values[0]), "number": values[1]}

    @staticmethod
    def _create_identifier_args(values):
        return {
            "identifier_type": IdentifierType.objects.get(name=values[0]),
            "nss": values[1],
            "url": values[2],
        }

    _CREATE_DICT_FUNCTION_MAP = (
        (Contributor, FKC_CONTRIBUTORS, _create_contributor_args),
        (StoryArcNumber, FKC_STORY_ARC_NUMBERS, _create_story_arc_number_args),
        (Identifier, FKC_IDENTIFIERS, _create_identifier_args),
    )

    def _bulk_create_dict_models(
        self, create_tuples_key, create_args_func, model, status
    ):
        """Bulk create a dict type m2m model."""
        create_tuples = self.metadata[FK_CREATE].pop(create_tuples_key, None)
        if not create_tuples:
            return

        create_objs = []
        for values_tuple in create_tuples:
            args = create_args_func(values_tuple)
            obj = model(**args)
            create_objs.append(obj)

        model.objects.bulk_create(
            create_objs,
            update_conflicts=True,
            update_fields=CREATE_DICT_UPDATE_FIELDS[model],
            unique_fields=model._meta.unique_together[0],  # type: ignore
        )
        count = len(create_objs)
        if count:
            vnp = model._meta.verbose_name_plural.title()
            self.log.info(f"Created {count} {vnp}.")
        status.add_complete(count)
        self.status_controller.update(status)

    def create_all_fks(self):
        """Bulk create all foreign keys."""
        fkc = self.metadata.get(FK_CREATE)
        if not fkc:
            return

        status = Status(ImportStatusTypes.CREATE_FKS, 0, fkc.pop(FKC_TOTAL_FKS, None))
        try:
            self.status_controller.start(status)

            for group_class, group_tree_counts in fkc.pop(
                FKC_CREATE_GROUPS, {}
            ).items():
                self._bulk_group_create(group_tree_counts, group_class, status)

            for group_class, group_tree_counts in fkc.pop(
                FKC_UPDATE_GROUPS, {}
            ).items():
                self._bulk_group_updater(group_tree_counts, group_class, status)

            self.bulk_folders_create(fkc.pop(FKC_FOLDER_PATHS, frozenset()), status)

            for named_class, names in fkc.pop(FKC_CREATE_FKS, {}).items():
                self._bulk_create_named_models(names, named_class, status)

            # These all depend on bulk_create_named_models running first
            for model, create_objs, func in self._CREATE_DICT_FUNCTION_MAP:
                self._bulk_create_dict_models(
                    create_objs,
                    func,
                    model,
                    status,
                )

        finally:
            self.metadata.pop(FK_CREATE, None)
            self.status_controller.finish(status)
        self.changed += status.complete if status.complete else 0

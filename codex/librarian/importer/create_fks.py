"""Create all missing comic foreign keys for an import.

So we may safely create the comics next.
"""

from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.functions.datetime import Now

from codex.librarian.importer.const import (
    BULK_UPDATE_FOLDER_FIELDS,
    CLASS_CUSTOM_COVER_GROUP_MAP,
    COUNT_FIELDS,
    CREATE_DICT_UPDATE_FIELDS,
    CUSTOM_COVER_UPDATE_FIELDS,
    GROUP_BASE_FIELDS,
    GROUP_UPDATE_FIELDS,
    IMPRINT,
    ISSUE_COUNT,
    NAMED_MODEL_UPDATE_FIELDS,
    PUBLISHER,
    SERIES,
    VOLUME_COUNT,
)
from codex.librarian.importer.status import ImportStatusTypes, status_notify
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
from codex.threads import QueuedThread


class CreateForeignKeysMixin(QueuedThread):
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

    @status_notify()
    def _bulk_group_create(self, group_tree_counts, group_class, status=None) -> int:
        """Bulk creates groups."""
        count = 0
        if not group_tree_counts:
            return count
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
        if status:
            status.complete = status.complete or 0
            status.complete += count
            self.status_controller.update(status)
        return count

    @status_notify()
    def _bulk_group_updater(self, group_tree_counts, group_class, status=None):
        """Bulk update groups."""
        count = 0
        if not group_tree_counts:
            return count
        update_groups = []
        for group_param_tuple, group_count in group_tree_counts.items():
            obj = self._update_group_obj(group_class, group_param_tuple, group_count)
            if obj:
                update_groups.append(obj)
        count_field = COUNT_FIELDS[group_class]
        group_class.objects.bulk_update(update_groups, fields=[count_field])
        count += len(update_groups)
        if count:
            vnp = group_class._meta.verbose_name_plural.title()
            self.log.info(f"Updated {count} {vnp}.")
        if status:
            status.complete = status.complete or 0
            status.complete += count
            self.status_controller.update(status)
        return count

    def _bulk_folders_create_add_folder(self, library, path, create_folders):
        """Add one folder to the create list."""
        parent_path = str(path.parent)
        parent = None
        try:
            parent = Folder.objects.get(path=parent_path)
        except Folder.DoesNotExist:
            if path.parent != Path(library.path):
                self.log.warning(
                    f"Can't find parent folder {parent_path}"
                    f" for {path} in library {library.path}"
                )
        folder = Folder(
            library=library,
            path=str(path),
            name=path.name,
            parent_folder=parent,
        )
        folder.presave()
        self._add_custom_cover_to_group(Folder, folder)
        create_folders.append(folder)

    def _bulk_folders_create_depth_level(self, library, paths, status):
        """Create a depth level of folders."""
        create_folders = []
        for path in sorted(paths):
            self._bulk_folders_create_add_folder(library, path, create_folders)
        Folder.objects.bulk_create(
            create_folders,
            update_conflicts=True,
            update_fields=BULK_UPDATE_FOLDER_FIELDS,
            unique_fields=Folder._meta.unique_together[0],  # type: ignore
        )
        count = len(create_folders)
        if status:
            status.complete = status.complete or 0
            status.complete += count
            self.status_controller.update(status)
        return count

    @status_notify()
    def bulk_folders_create(self, folder_paths: set, library, status=None):
        """Create folders breadth first."""
        count = 0
        if not folder_paths:
            return count
        # group folder paths by depth
        folder_path_dict = {}
        for path_str in folder_paths:
            path = Path(path_str)
            path_length = len(path.parts)
            if path_length not in folder_path_dict:
                folder_path_dict[path_length] = set()
            folder_path_dict[path_length].add(path)

        # create each depth level first to ensure we can assign parents
        for _, paths in sorted(folder_path_dict.items()):
            count += self._bulk_folders_create_depth_level(library, paths, status)

        if count:
            self.log.info(f"Created {count} Folders.")
        return count

    @status_notify()
    def _bulk_create_named_models(self, names, named_class, status=None):
        """Bulk create named models."""
        count = len(names)
        if not count:
            return count
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
        if status:
            status.complete = status.complete or 0
            status.complete += count
            self.status_controller.update(status)
        return count

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

    @status_notify()
    def _bulk_create_dict_models(
        self, create_tuples, create_args_method, model, status=None
    ):
        """Bulk create a dict type m2m model."""
        if not create_tuples:
            return 0

        create_objs = []
        for values_tuple in create_tuples:
            args = create_args_method(values_tuple)
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
        if status:
            status.complete = status.complete or 0
            status.complete += count
            self.status_controller.update(status)
        return count

    def create_all_fks(self, library, create_data) -> int:
        """Bulk create all foreign keys."""
        (
            create_groups,
            update_groups,
            create_folder_paths,
            create_fks,
            create_contributors,
            create_story_arc_numbers,
            create_identifiers,
            total_fks,
        ) = create_data

        status = Status(ImportStatusTypes.CREATE_FKS, 0, total_fks)
        try:
            self.status_controller.start(status)

            for group_class, group_tree_counts in create_groups.items():
                count = self._bulk_group_create(
                    group_tree_counts,
                    group_class,
                    status=status,
                )
                status.add_complete(count)

            for group_class, group_tree_counts in update_groups.items():
                count = self._bulk_group_updater(
                    group_tree_counts,
                    group_class,
                    status=status,
                )
                status.add_complete(count)

            count = self.bulk_folders_create(
                sorted(create_folder_paths),
                library,
                status=status,
            )
            status.add_complete(count)

            for named_class, names in create_fks.items():
                count = self._bulk_create_named_models(
                    names,
                    named_class,
                    status=status,
                )
                status.add_complete(count)

            # These all depend on bulk_create_named_models running first
            create_dict_data = (
                (Contributor, create_contributors, self._create_contributor_args),
                (
                    StoryArcNumber,
                    create_story_arc_numbers,
                    self._create_story_arc_number_args,
                ),
                (Identifier, create_identifiers, self._create_identifier_args),
            )
            for model, create_objs, func in create_dict_data:
                count = self._bulk_create_dict_models(
                    create_objs,
                    func,
                    model,
                    status=status,
                )
                status.add_complete(count)

        finally:
            self.status_controller.finish(status)
        return status.complete if status.complete else 0

    @status_notify(ImportStatusTypes.COVERS_MODIFIED, updates=False)
    def update_custom_covers(
        self, update_covers_qs, link_cover_pks, status=None
    ) -> int:
        """Update Custom Covers."""
        count = 0
        update_covers_count = update_covers_qs.count()
        if not update_covers_count:
            return count
        if status:
            status.total = update_covers_count
        now = Now()

        update_covers = []
        for cover in update_covers_qs.only(*CUSTOM_COVER_UPDATE_FIELDS):
            cover.updated_at = now
            cover.presave()
            update_covers.append(cover)

        if update_covers:
            CustomCover.objects.bulk_update(update_covers, CUSTOM_COVER_UPDATE_FIELDS)
            update_cover_pks = update_covers_qs.values_list("pk", flat=True)
            link_cover_pks.update(update_cover_pks)
            self._remove_covers(update_cover_pks, custom=True)  # type: ignore
            count = len(update_covers)
            if status:
                status.add_complete(count)
        return count

    @status_notify(ImportStatusTypes.COVERS_CREATED, updates=False)
    def create_custom_covers(
        self, create_cover_paths, library, link_cover_pks, status=None
    ) -> int:
        """Create Custom Covers."""
        count = 0
        if not create_cover_paths:
            return count
        if status:
            status.total = len(create_cover_paths)

        create_covers = []
        for path in create_cover_paths:
            cover = CustomCover(library=library, path=path)
            cover.presave()
            create_covers.append(cover)

        if create_covers:
            objs = CustomCover.objects.bulk_create(
                create_covers,
                update_conflicts=True,
                update_fields=("path", "stat"),
                unique_fields=CustomCover._meta.unique_together[0],
            )
            created_pks = frozenset(obj.pk for obj in objs)
            link_cover_pks.update(created_pks)
            count = len(created_pks)
            if status:
                status.add_complete(count)
        return count

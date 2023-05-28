"""Create all missing comic foreign keys for an import.

So we may safely create the comics next.
"""
from itertools import chain
from pathlib import Path

from codex.librarian.importer.status import ImportStatusTypes, status_notify
from codex.models import (
    Creator,
    CreatorPerson,
    CreatorRole,
    Folder,
    Imprint,
    Publisher,
    Series,
    StoryArc,
    StoryArcNumber,
    Volume,
)
from codex.status import Status
from codex.threads import QueuedThread

BULK_UPDATE_FOLDER_MODIFIED_FIELDS = ("stat", "updated_at")
_COUNT_FIELDS = {Series: "volume_count", Volume: "issue_count"}
_GROUP_UPDATE_FIELDS = {
    Publisher: ("name",),
    Imprint: ("name", "publisher"),
    Series: ("name", "imprint"),
    Volume: ("name", "publisher", "imprint", "series"),
}
_NAMED_MODEL_UPDATE_FIELDS = ("name",)

_CREATE_DICT_UPDATE_FIELDS = {
    Creator: ("person", "role"),
    StoryArcNumber: ("story_arc", "number"),
}


class CreateForeignKeysMixin(QueuedThread):
    """Methods for creating foreign keys."""

    @staticmethod
    def _create_group_obj(group_class, group_param_tuple, count_dict):
        """Create a set of browser group objects."""
        defaults = {"name": group_param_tuple[-1]}
        if group_class in (Imprint, Series, Volume):
            defaults["publisher"] = Publisher.objects.get(name=group_param_tuple[0])
        if group_class in (Series, Volume):
            defaults["imprint"] = Imprint.objects.get(
                publisher=defaults["publisher"],
                name=group_param_tuple[1],
            )

        if group_class is Series:
            count_field = _COUNT_FIELDS[group_class]
            defaults["volume_count"] = count_dict.get(count_field)
        elif group_class is Volume:
            defaults["series"] = Series.objects.get(
                publisher=defaults["publisher"],
                imprint=defaults["imprint"],
                name=group_param_tuple[2],
            )
            count_field = _COUNT_FIELDS[group_class]
            defaults["issue_count"] = count_dict.get(count_field)

        return group_class(**defaults)

    @staticmethod
    def _update_group_obj(group_class, group_param_tuple, count_dict, count_field):
        """Update group counts for a Series or Volume."""
        count = count_dict.get(count_field)
        if count is None:
            return None
        search_kwargs = {
            "publisher__name": group_param_tuple[0],
            "imprint__name": group_param_tuple[1],
            "name": group_param_tuple[-1],
        }
        if group_class == Volume:
            search_kwargs["series__name"] = group_param_tuple[2]

        obj = group_class.objects.get(**search_kwargs)
        obj_count = getattr(obj, count_field)
        if obj_count is None or count > obj_count:
            setattr(obj, count_field, count)
        else:
            obj = None
        return obj

    @status_notify()
    def _bulk_group_creator(self, group_tree_counts, group_class, status=None):
        """Bulk creates groups."""
        count = 0
        if not group_tree_counts:
            return count
        create_groups = []
        for group_param_tuple, count_dict in group_tree_counts.items():
            obj = self._create_group_obj(group_class, group_param_tuple, count_dict)
            create_groups.append(obj)
        update_fields = _GROUP_UPDATE_FIELDS[group_class]
        group_class.objects.bulk_create(
            create_groups,
            update_conflicts=True,
            update_fields=update_fields,
            unique_fields=group_class._meta.unique_together[0],
        )
        count += len(create_groups)
        self.log.info(f"Created {count} {group_class.__name__}s.")
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
        count_field = _COUNT_FIELDS[group_class]
        for group_param_tuple, count_dict in group_tree_counts.items():
            obj = self._update_group_obj(
                group_class, group_param_tuple, count_dict, count_field
            )
            if obj:
                update_groups.append(obj)
        group_class.objects.bulk_update(update_groups, fields=[count_field])
        count += len(update_groups)
        self.log.info(f"Updated {count} {group_class.__name__}s.")
        if status:
            status.complete = status.complete or 0
            status.complete += count
            self.status_controller.update(status)
        return count

    @status_notify()
    def bulk_folders_create(self, folder_paths, library, status=None):
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
            create_folders = []
            for path in sorted(paths):
                parent_path = str(path.parent)
                parent = None
                try:
                    parent = Folder.objects.get(path=parent_path)
                except Folder.DoesNotExist:
                    if path.parent != Path(library.path):
                        self.log.exception(
                            f"Can't find parent folder {parent_path}"
                            f" for {path} in library {library.path}"
                        )
                folder = Folder(
                    library=library,
                    path=str(path),
                    name=path.name,
                    parent_folder=parent,
                )
                folder.set_stat()
                create_folders.append(folder)
            Folder.objects.bulk_create(
                create_folders,
                update_conflicts=True,
                update_fields=BULK_UPDATE_FOLDER_MODIFIED_FIELDS,
                unique_fields=Folder._meta.unique_together[0],  # type: ignore
            )
            count += len(create_folders)
            if status:
                status.complete = status.complete or 0
                status.complete += len(create_folders)
                self.status_controller.update(status)

        self.log.info(f"Created {count} Folders.")
        return count

    @status_notify()
    def _bulk_create_named_models(self, names, named_class, status=None):
        """Bulk create named models."""
        count = len(names)
        if not count:
            return count
        create_named_objs = []
        for name in names:
            named_obj = named_class(name=name)
            create_named_objs.append(named_obj)

        named_class.objects.bulk_create(
            create_named_objs,
            update_conflicts=True,
            update_fields=_NAMED_MODEL_UPDATE_FIELDS,
            unique_fields=named_class._meta.unique_together[0],
        )
        self.log.info(f"Created {count} {named_class.__name__}s.")
        if status:
            status.complete = status.complete or 0
            status.complete += count
            self.status_controller.update(status)
        return count

    @staticmethod
    def _create_creator(role_name, person_name):
        role = CreatorRole.objects.get(name=role_name) if role_name else None
        person = CreatorPerson.objects.get(name=person_name)
        return Creator(role=role, person=person)

    @staticmethod
    def _create_story_arc_number(name, number):
        story_arc = StoryArc.objects.get(name=name)
        return StoryArcNumber(story_arc=story_arc, number=number)

    def _bulk_create_dict_models(
        self, create_tuples, create_method, model, status=None
    ):
        """Bulk create a dict type m2m model."""
        if not create_tuples:
            return 0

        create_objs = []
        for key, value in create_tuples:
            obj = create_method(key, value)
            create_objs.append(obj)

        model.objects.bulk_create(
            create_objs,
            update_conflicts=True,
            update_fields=_CREATE_DICT_UPDATE_FIELDS[model],
            unique_fields=model._meta.unique_together[0],  # type: ignore
        )
        count = len(create_objs)
        self.log.info(f"Created {count} {model.__class__.__name__}s.")
        if status:
            status.complete = status.complete or 0
            status.complete += count
            self.status_controller.update(status)
        return count

    @status_notify()
    def _bulk_create_creators(self, create_creator_tuples, status=None):
        """Bulk create creators."""
        return self._bulk_create_dict_models(
            create_creator_tuples,
            self._create_creator,
            Creator,
            status,
        )

    @status_notify()
    def _bulk_create_story_arc_numbers(
        self, create_story_arc_number_tuples, status=None
    ):
        """Bulk create story_arc_numbers."""
        return self._bulk_create_dict_models(
            create_story_arc_number_tuples,
            self._create_story_arc_number,
            StoryArcNumber,
            status,
        )

    @staticmethod
    def _get_create_fks_totals(create_data):
        (
            create_groups,
            update_groups,
            create_folder_paths,
            create_fks,
            create_creators,
            create_story_arc_numbers,
        ) = create_data
        total_fks = 0
        for data_group in chain(
            create_groups.values(), update_groups.values(), create_fks.values()
        ):
            total_fks += len(data_group)
        total_fks += (
            len(create_folder_paths)
            + len(create_creators)
            + len(create_story_arc_numbers)
        )
        return total_fks

    def create_all_fks(self, library, create_data):
        """Bulk create all foreign keys."""
        total_fks = self._get_create_fks_totals(create_data)
        status = Status(ImportStatusTypes.CREATE_FKS, 0, total_fks)
        try:
            self.status_controller.start(status)
            (
                create_groups,
                update_groups,
                create_folder_paths,
                create_fks,
                create_creators,
                create_story_arc_numbers,
            ) = create_data

            for group_class, group_tree_counts in create_groups.items():
                status.complete += self._bulk_group_creator(  # type: ignore
                    group_tree_counts,
                    group_class,
                    status=status,
                )

            for group_class, group_tree_counts in update_groups.items():
                status.complete += self._bulk_group_updater(  # type: ignore
                    group_tree_counts,
                    group_class,
                    status=status,
                )

            status.complete += self.bulk_folders_create(  # type: ignore
                sorted(create_folder_paths),
                library,
                status=status,
            )

            for named_class, names in create_fks.items():
                status.complete += self._bulk_create_named_models(
                    names,
                    named_class,
                    status=status,
                )

            # This must happen after creator_fks created by create_named_models
            status.complete += self._bulk_create_creators(
                create_creators,
                status=status,
            )

            # This must happen after story_arc_fks created by create_named_models
            status.complete += self._bulk_create_story_arc_numbers(
                create_story_arc_numbers,
                status=status,
            )

        finally:
            self.status_controller.finish(status)
        return status.complete

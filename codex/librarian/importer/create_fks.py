"""Create all missing comic foreign keys for an import.

So we may safely create the comics next.
"""
from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.importer.status import ImportStatusTypes
from codex.models import (
    Credit,
    CreditPerson,
    CreditRole,
    Folder,
    Imprint,
    Publisher,
    Series,
    Volume,
)
from codex.threads import QueuedThread

_BULK_UPDATE_FOLDER_MODIFIED_FIELDS = ("stat", "updated_at")
_COUNT_FIELDS = {Series: "volume_count", Volume: "issue_count"}
_GROUP_UPDATE_FIELDS = {
    Publisher: ("name",),
    Imprint: ("name", "publisher"),
    Series: ("name", "imprint"),
    Volume: ("name", "publisher", "imprint", "series"),
}
_NAMED_MODEL_UPDATE_FIELDS = ("name",)
_CREDIT_UPDATE_FIELDS = ("person", "role")


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

        group_obj = group_class(**defaults)
        return group_obj

    @staticmethod
    def _update_group_obj(group_class, group_param_tuple, count_dict, count_field):
        """Update group counts for a Series or Volume."""
        if count_dict is None:
            # TODO this is never none now.
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
        count = count_dict.get(count_field)
        if obj_count is None or obj_count < count:
            setattr(obj, count_field, count)
        else:
            obj = None
        return obj

    def bulk_group_creator(self, group_tree_counts, _status_args, group_class):
        """Bulk creates groups."""
        if not group_tree_counts:
            return 0
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
        this_count = len(create_groups)
        if this_count:
            self.log.debug(f"Created {this_count} {group_class.__name__}s.")

        return this_count

    def bulk_group_updater(self, group_tree_counts, _status_args, group_class):
        """Bulk update groups."""
        if not group_tree_counts:
            return 0
        update_groups = []
        count_field = _COUNT_FIELDS[group_class]
        for group_param_tuple, count_dict in group_tree_counts.items():
            obj = self._update_group_obj(
                group_class, group_param_tuple, count_dict, count_field
            )
            if obj:
                update_groups.append(obj)
        group_class.objects.bulk_update(update_groups, fields=[count_field])
        count = len(update_groups)
        if count:
            self.log.debug(f"Updated {count} {group_class.__name__}s.")
        return count

    def bulk_folders_modified(self, paths, _status_args, library):
        """Update folders stat and nothing else."""
        if not paths:
            return False
        folders = Folder.objects.filter(library=library, path__in=paths).only(
            "stat", "updated_at"
        )
        update_folders = []
        now = Now()
        for folder in folders.iterator():
            if Path(folder.path).exists():
                folder.set_stat()
                folder.updated_at = now
                update_folders.append(folder)
        Folder.objects.bulk_update(
            update_folders, fields=_BULK_UPDATE_FOLDER_MODIFIED_FIELDS
        )
        count = len(update_folders)
        self.log.debug(f"Modified {count} folders")
        return count

    def bulk_folders_create(self, folder_paths, status_args, library):
        """Create folders breadth first."""
        if not folder_paths:
            return False
        # group folder paths by depth
        folder_path_dict = {}
        for path_str in folder_paths:
            path = Path(path_str)
            path_length = len(path.parts)
            if path_length not in folder_path_dict:
                folder_path_dict[path_length] = set()
            folder_path_dict[path_length].add(path)

        # create each depth level first to ensure we can assign parents
        total_count = 0
        for _, paths in sorted(folder_path_dict.items()):
            create_folders = []
            for path in sorted(paths):
                parent_path = str(path.parent)
                parent = None
                try:
                    parent = Folder.objects.get(path=parent_path)
                except Folder.DoesNotExist:
                    if parent_path != library.path:
                        self.log.error(
                            f"Can't find parent folder {parent_path} for {path}"
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
                update_fields=_BULK_UPDATE_FOLDER_MODIFIED_FIELDS,
                unique_fields=Folder._meta.unique_together[0],
            )
            total_count += len(create_folders)
            if status_args and status_args.total:
                status_args.since = self.status_controller.update(
                    ImportStatusTypes.CREATE_FKS,
                    status_args.count + total_count,
                    status_args.total,
                    since=status_args.since,
                )
        if total_count:
            self.log.debug(f"Created {total_count} Folders.")
        return total_count

    def bulk_create_named_models(self, names, _status_args, named_class):
        """Bulk create named models."""
        if not names:
            return False
        count = len(names)
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
        self.log.debug(f"Created {count} {named_class.__name__}s.")
        return count

    def bulk_create_credits(self, create_credit_tuples, _status_args):
        """Bulk create credits."""
        if not create_credit_tuples:
            return False

        create_credits = []
        for role_name, person_name in create_credit_tuples:
            if role_name:
                role = CreditRole.objects.get(name=role_name)
            else:
                role = None
            person = CreditPerson.objects.get(name=person_name)
            credit = Credit(role=role, person=person)

            create_credits.append(credit)

        Credit.objects.bulk_create(
            create_credits,
            update_conflicts=True,
            update_fields=_CREDIT_UPDATE_FIELDS,
            unique_fields=Credit._meta.unique_together[0],
        )
        create_count = len(create_credits)
        self.log.debug(f"Created {create_count} Credits.")
        return create_count

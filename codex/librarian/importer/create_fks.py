"""Create all missing comic foreign keys for an import.

So we may safely create the comics next.
"""
import logging
from pathlib import Path
from time import time

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


class CreateForeignKeysMixin(QueuedThread):
    """Methods for creating foreign keys."""

    @staticmethod
    def _create_group_obj(group_class, group_param_tuple, count):
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
            defaults["volume_count"] = count
        elif group_class is Volume:
            defaults["series"] = Series.objects.get(
                publisher=defaults["publisher"],
                imprint=defaults["imprint"],
                name=group_param_tuple[2],
            )
            defaults["issue_count"] = count

        group_obj = group_class(**defaults)
        return group_obj

    @staticmethod
    def _update_group_obj(group_class, group_param_tuple, count, count_field):
        """Update group counts for a Series or Volume."""
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
        if obj_count is None or obj_count < count:
            setattr(obj, count_field, count)
        else:
            obj = None
        return obj

    @classmethod
    def _bulk_group_creator(cls, group_tree_counts, group_class):
        """Bulk creates groups."""
        create_groups = []
        for group_param_tuple, count in group_tree_counts.items():
            obj = cls._create_group_obj(group_class, group_param_tuple, count)
            create_groups.append(obj)
        group_class.objects.bulk_create(create_groups)
        return len(create_groups)

    @classmethod
    def _bulk_group_updater(cls, group_tree_counts, group_class):
        """Bulk update groups."""
        update_groups = []
        count_field = _COUNT_FIELDS[group_class]
        for group_param_tuple, count in group_tree_counts.items():
            obj = cls._update_group_obj(
                group_class, group_param_tuple, count, count_field
            )
            if obj:
                update_groups.append(obj)
        count = group_class.objects.bulk_update(update_groups, fields=[count_field])
        return count

    def _bulk_create_or_update_groups(
        self, all_operation_groups, func, log_tion, log_verb
    ):
        """Create missing groups breadth first."""
        if not all_operation_groups:
            return False
        num_operation_groups = 0
        for group_class, group_tree_counts in all_operation_groups.items():
            if not group_tree_counts:
                continue
            self.log.debug(
                f"Preparing {len(group_tree_counts)} "
                f"{group_class.__name__}s for {log_tion}..."
            )
            count = func(group_tree_counts, group_class)

            num_operation_groups += count
            if count:
                level = logging.INFO
            else:
                level = logging.DEBUG
            self.log.log(level, f"{log_verb} {count} {group_class.__name__}s.")

        return num_operation_groups

    def bulk_folders_modified(self, library, paths):
        """Update folders stat and nothing else."""
        if not paths:
            return False
        self.log.debug(f"Preparing {len(paths)} folders for modification...")
        folders = Folder.objects.filter(library=library, path__in=paths).only(
            "stat", "updated_at"
        )
        update_folders = []
        now = Now()
        for folder in folders:
            if Path(folder.path).exists():
                folder.set_stat()
                folder.updated_at = now
                update_folders.append(folder)
        count = Folder.objects.bulk_update(
            update_folders, fields=_BULK_UPDATE_FOLDER_MODIFIED_FIELDS
        )
        if count:
            level = logging.INFO
        else:
            count = 0
            level = logging.DEBUG
        self.log.log(level, f"Modified {count} folders")

        return count

    def bulk_folders_create(self, library, folder_paths):
        """Create folders breadth first."""
        if not folder_paths:
            return False

        num_folder_paths = len(folder_paths)
        self.log.debug(f"Preparing {num_folder_paths} folders for creation.")
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
            Folder.objects.bulk_create(create_folders)
            count = len(create_folders)
            total_count += count
            if count:
                level = logging.INFO
            else:
                level = logging.DEBUG
            self.log.log(level, f"Created {total_count}/{num_folder_paths} Folders.")
        return total_count

    def _bulk_create_named_models(self, group_class, names):
        """Bulk create named models."""
        if not names:
            return False
        count = len(names)
        self.log.debug(f"Preparing {count} {group_class.__name__}s for creation...")
        create_named_objs = []
        for name in names:
            named_obj = group_class(name=name)
            create_named_objs.append(named_obj)

        group_class.objects.bulk_create(create_named_objs)
        if count:
            level = logging.INFO
        else:
            level = logging.DEBUG
        self.log.log(level, f"Created {count} {group_class.__name__}s.")
        return count

    def _bulk_create_credits(self, create_credit_tuples):
        """Bulk create credits."""
        if not create_credit_tuples:
            return False

        self.log.debug(f"Preparing {len(create_credit_tuples)} credits for creation...")
        create_credits = []
        for role_name, person_name in create_credit_tuples:
            if role_name:
                role = CreditRole.objects.get(name=role_name)
            else:
                role = None
            person = CreditPerson.objects.get(name=person_name)
            credit = Credit(role=role, person=person)

            create_credits.append(credit)

        Credit.objects.bulk_create(create_credits)
        count = len(create_credits)
        if count:
            level = logging.INFO
        else:
            level = logging.DEBUG
        self.log.log(level, f"Created {count} Credits.")

        return count

    def _init_create_fk_librarian_status(
        self,
        create_groups,
        update_groups,
        create_folder_paths,
        create_fks,
        create_credits,
    ):
        total_fks = 0
        for groups in create_groups.values():
            total_fks += len(groups)
        for groups in update_groups.values():
            total_fks += len(groups)
        total_fks += len(create_folder_paths)
        for names in create_fks.values():
            total_fks += len(names)
        total_fks += len(create_credits)
        self.status_controller.start(ImportStatusTypes.CREATE_FKS, total_fks)
        return total_fks

    def _status_update(self, completed, total_fks, since):
        since = self.status_controller.update(
            ImportStatusTypes.CREATE_FKS, completed, total_fks, since=since
        )
        return since

    def bulk_create_all_fks(
        self,
        library,
        create_fks,
        create_groups,
        update_groups,
        create_folder_paths,
        create_credits,
    ) -> bool:
        """Bulk create all foreign keys."""
        try:
            total_fks = self._init_create_fk_librarian_status(
                create_groups,
                update_groups,
                create_folder_paths,
                create_fks,
                create_credits,
            )
            since = time()
            self.log.debug(f"Creating comic foreign keys for {library.path}...")
            count = 0
            count += self._bulk_create_or_update_groups(
                create_groups, self._bulk_group_creator, "creation", "Created"
            )
            since = self._status_update(count, total_fks, since)
            count += self._bulk_create_or_update_groups(
                update_groups, self._bulk_group_updater, "update", "Updated"
            )
            since = self._status_update(count, total_fks, since)

            count += self.bulk_folders_create(library, create_folder_paths)
            since = self._status_update(count, total_fks, since)

            for cls, names in create_fks.items():
                count += self._bulk_create_named_models(cls, names)
                since = self._status_update(count, total_fks, since)

            # This must happen after credit_fks created by create_named_models
            count += self._bulk_create_credits(create_credits)
            return count > 0
        finally:
            self.status_controller.finish(ImportStatusTypes.CREATE_FKS)

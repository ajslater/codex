"""Batched jobs for import."""
from itertools import islice
from time import time

from codex.librarian.importer.deleted import DeletedMixin
from codex.librarian.importer.failed_imports import FailedImportsMixin
from codex.librarian.importer.moved import MovedMixin
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.importer.update_comics import UpdateComicsMixin
from codex.models import Comic, Credit
from codex.settings.settings import MAX_IMPORT_BATCH_SIZE

_CREDIT_FK_NAMES = ("role", "person")


class BatchMixin(DeletedMixin, UpdateComicsMixin, FailedImportsMixin, MovedMixin):
    """Methods that are batched."""

    def batch_db_op(
        self, library, data, func, status, args=None, count=0, total=0, since=None
    ):
        """Run a function batched for memory contrainsts bracketed by status changes."""
        num_elements = len(data)
        finish = total == 0
        this_count = 0
        if since is None:
            since = time()
        try:
            if not num_elements:
                return count
            if total:
                complete = count
            else:
                complete = None

            if not total:
                total = num_elements
                self.status_controller.start(status, complete, total)
            batch_size = min(num_elements, MAX_IMPORT_BATCH_SIZE)
            start = 0
            end = start + batch_size
            is_dict = isinstance(data, dict)
            if not is_dict:
                data = list(data)
            if args is None:
                args = ()
            while start < num_elements:
                if is_dict:
                    batch = dict(islice(data.items(), start, end))  # type: ignore
                else:
                    batch = data[start:end]
                all_args = (library, batch, count, total, *args)
                this_count += int(func(*all_args))
                start = end
                end = start + batch_size
                if total:
                    since = self.status_controller.update(
                        status, count + this_count, total, since=since
                    )

        finally:
            if finish:
                self.status_controller.finish(status)

        return this_count

    def _move_and_modify_dirs(self, library, task):
        """Move files and dirs and modify dirs."""
        changed = self.batch_db_op(
            library,
            task.dirs_moved,
            self.bulk_folders_moved,
            ImportStatusTypes.DIRS_MOVED,
        )
        task.dirs_moved = None
        changed += self.batch_db_op(
            library,
            task.files_moved,
            self.bulk_comics_moved,
            ImportStatusTypes.FILES_MOVED,
        )
        task.files_moved = None
        changed += self.batch_db_op(
            library,
            task.dirs_modified,
            self.bulk_folders_modified,
            ImportStatusTypes.DIRS_MODIFIED,
        )
        task.dirs_modified = None
        return changed

    @staticmethod
    def _get_query_fks_totals(fks):
        """Get the query foreign keys totals."""
        fks_total = 0
        for key, objs in fks.items():
            if key == "group_trees":
                for groups in objs.values():
                    fks_total += len(groups)
            else:
                fks_total += len(objs)
        return fks_total

    def query_all_missing_fks(self, library, fks):
        """Get objects to create by querying existing objects for the proposed fks."""
        create_credits = set()
        create_groups = {}
        update_groups = {}
        create_folder_paths = set()
        create_fks = {}
        try:
            self.log.debug(
                f"Querying existing foreign keys for comics in {library.path}"
            )
            count = 0
            fks_total = self._get_query_fks_totals(fks)
            self.status_controller.start(
                ImportStatusTypes.QUERY_MISSING_FKS, 0, fks_total
            )

            if "credits" in fks:
                count += self.batch_db_op(
                    library,
                    fks.pop("credits"),
                    self.query_missing_credits,
                    ImportStatusTypes.QUERY_MISSING_FKS,
                    args=(create_credits,),
                    count=count,
                    total=fks_total,
                )
                if num_create_credits := len(create_credits):
                    self.log.info(f"Prepared {num_create_credits} new credits.")

            if "group_trees" in fks:
                for group_class, groups in fks.pop("group_trees").items():
                    count += self.batch_db_op(
                        library,
                        groups,
                        self.query_missing_group,
                        ImportStatusTypes.QUERY_MISSING_FKS,
                        args=(group_class, create_groups, update_groups),
                        count=count,
                        total=fks_total,
                    )
                if num_create_groups := len(create_groups):
                    self.log.info(f"Prepared {num_create_groups} new groups.")

            if "comic_paths" in fks:
                count += self.batch_db_op(
                    library,
                    fks.pop("comic_paths"),
                    self.query_missing_folder_paths,
                    ImportStatusTypes.QUERY_MISSING_FKS,
                    args=(create_folder_paths,),
                    count=count,
                    total=fks_total,
                )
                if num_create_folder_paths := len(create_folder_paths):
                    self.log.info(f"Prepared {num_create_folder_paths} new folders.")

            for fk_field in sorted(fks.keys()):
                names = fks.pop(fk_field)
                if fk_field in _CREDIT_FK_NAMES:
                    base_cls = Credit
                else:
                    base_cls = Comic
                count += self.batch_db_op(
                    library,
                    names,
                    self.query_missing_simple_models,
                    ImportStatusTypes.QUERY_MISSING_FKS,
                    args=(create_fks, base_cls, fk_field, "name"),
                    count=count,
                    total=fks_total,
                )
                if num_names := len(names):
                    self.log.info(f"Prepared {num_names} new {fk_field}.")
        finally:
            self.status_controller.finish(ImportStatusTypes.QUERY_MISSING_FKS)

        return (
            create_fks,
            create_groups,
            update_groups,
            create_folder_paths,
            create_credits,
        )

    @staticmethod
    def _get_create_fks_totals(
        create_groups, update_groups, create_folder_paths, create_fks, create_credits
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
        return total_fks

    def bulk_create_all_fks(
        self,
        library,
        create_fks,
        create_groups,
        update_groups,
        create_folder_paths,
        create_credits,
    ):
        """Bulk create all foreign keys."""
        try:
            count = 0
            total_fks = self._get_create_fks_totals(
                create_groups,
                update_groups,
                create_folder_paths,
                create_fks,
                create_credits,
            )
            status = ImportStatusTypes.CREATE_FKS
            self.status_controller.start(status, 0, total_fks)

            self.log.debug(f"Creating comic foreign keys for {library.path}...")

            self.log.debug(f"Preparing {len(create_groups)} groups for creation..")
            for group_class, group_tree_counts in create_groups.items():
                count += self.batch_db_op(
                    library,
                    group_tree_counts,
                    self.bulk_group_creator,
                    status,
                    args=(group_class,),
                    count=count,
                    total=total_fks,
                )

            self.log.debug(f"Preparing {len(update_groups)} groups for update...")
            for group_class, group_tree_counts in update_groups.items():
                count += self.batch_db_op(
                    library,
                    group_tree_counts,
                    self.bulk_group_updater,
                    status,
                    args=(group_class,),
                    count=count,
                    total=total_fks,
                )

            count += self.batch_db_op(
                library,
                sorted(create_folder_paths),
                self.bulk_folders_create,
                status,
                count=count,
                total=total_fks,
            )

            for named_cls, names in create_fks.items():
                count += self.batch_db_op(
                    library,
                    names,
                    self.bulk_create_named_models,
                    status,
                    args=(named_cls,),
                    count=count,
                    total=total_fks,
                )

            # This must happen after credit_fks created by create_named_models
            count += self.batch_db_op(
                library,
                create_credits,
                self.bulk_create_credits,
                status,
                count=count,
                total=total_fks,
            )
            return count
        finally:
            self.status_controller.finish(ImportStatusTypes.CREATE_FKS)

    def _create_comic_relations(self, library, fks):
        """Query all foreign keys to determine what needs creating, then create them."""
        if not fks:
            return 0

        (
            create_fks,
            create_groups,
            update_groups,
            create_paths,
            create_credits,
        ) = self.query_all_missing_fks(library, fks)

        count = self.bulk_create_all_fks(
            library,
            create_fks,
            create_groups,
            update_groups,
            create_paths,
            create_credits,
        )
        return count

    def _update_create_and_link_comics(
        self, library, modified_paths, created_paths, mds, m2m_mds
    ):
        """Update, create and link comics."""
        update_count = create_count = 0

        update_count = self.batch_db_op(
            library,
            modified_paths,
            self.bulk_update_comics,
            ImportStatusTypes.FILES_MODIFIED,
            args=(created_paths, mds),
        )

        create_count = self.batch_db_op(
            library,
            created_paths,
            self.bulk_create_comics,
            ImportStatusTypes.FILES_CREATED,
            args=(mds,),
        )

        linked_count = self.batch_db_op(
            library,
            m2m_mds,
            self.bulk_query_and_link_comic_m2m_fields,
            ImportStatusTypes.LINK_M2M_FIELDS,
        )
        if linked_count:
            self.log.info(f"Linked {linked_count} comics to tags.")

        imported_count = update_count + create_count
        if imported_count:
            self.log.info(f"Updated {update_count} and created {create_count} comics.")
        return imported_count

    def _bulk_fail_imports(self, library, failed_imports):
        """Handle failed imports."""
        is_new_failed_imports = 0
        try:
            update_fis = {}
            create_fis = {}
            delete_fi_paths = set()
            self.batch_db_op(
                library,
                failed_imports,
                self.query_failed_imports,
                ImportStatusTypes.FAILED_IMPORTS_QUERY,
                args=(update_fis, create_fis, delete_fi_paths),
            )

            self.batch_db_op(
                library,
                update_fis,
                self.bulk_update_failed_imports,
                ImportStatusTypes.FAILED_IMPORTS_MODIFIED,
            )

            is_new_failed_imports = self.batch_db_op(
                library,
                create_fis,
                self.bulk_create_failed_imports,
                ImportStatusTypes.FAILED_IMPORTS_CREATE,
            )

            self.batch_db_op(
                library,
                delete_fi_paths,
                self.bulk_cleanup_failed_imports,
                ImportStatusTypes.FAILED_IMPORTS_CLEAN,
            )
        except Exception as exc:
            self.log.exception(exc)
        return is_new_failed_imports

    def _delete(self, library, task):
        """Delete files and folders."""
        changed = self.batch_db_op(
            library,
            task.dirs_deleted,
            self.bulk_folders_deleted,
            ImportStatusTypes.DIRS_DELETED,
        )
        task.dirs_deleted = None
        changed += self.batch_db_op(
            library,
            task.files_deleted,
            self.bulk_comics_deleted,
            ImportStatusTypes.FILES_DELETED,
        )
        task.files_deleted = None
        return changed

"""Batched jobs for import."""
from itertools import islice
from time import time

from codex.librarian.importer.deleted import DeletedMixin
from codex.librarian.importer.failed_imports import FailedImportsMixin
from codex.librarian.importer.moved import MovedMixin
from codex.librarian.importer.status import ImportStatusTypes, StatusArgs
from codex.librarian.importer.update_comics import UpdateComicsMixin
from codex.models import Comic, Credit
from codex.settings.settings import MAX_IMPORT_BATCH_SIZE

_CREDIT_FK_NAMES = ("role", "person")


class BatchMixin(DeletedMixin, UpdateComicsMixin, FailedImportsMixin, MovedMixin):
    """Methods that are batched."""

    def _run_one_db_op_batch(
        self,
        func,
        data,
        args,
        status_args,
        batch_size,
        start,
        end,
        this_count,
        status,
        is_dict,
    ):
        """Run one batch of data with the designated function."""
        if status_args.total and start > 0:
            status_args.count += this_count
            status_args.since = self.status_controller.update(
                status,
                status_args.count,
                status_args.total,
                since=status_args.since,
            )
        if is_dict:
            batch = dict(islice(data.items(), start, end))  # type: ignore
        else:
            batch = data[start:end]
        all_args = (batch, status_args, *args)
        this_count += int(func(*all_args))
        start = end
        end = start + batch_size

        return this_count, start, end

    def batch_db_op(self, func, data, status, status_args=None, args=None):
        """Run a function batched for memory contrainsts bracketed by status changes."""
        this_count = 0
        num_elements = len(data)
        start_and_finish = status_args is not None
        try:
            if not num_elements:
                return this_count
            if not status_args:
                status_args = StatusArgs(0, num_elements, time())
            if start_and_finish:
                self.status_controller.start(
                    status, status_args.count, status_args.total
                )

            batch_size = min(num_elements, MAX_IMPORT_BATCH_SIZE)
            start = 0
            end = start + batch_size
            is_dict = isinstance(data, dict)
            if not is_dict:
                data = list(data)
            if args is None:
                args = ()
            while start < num_elements:
                this_count, start, end = self._run_one_db_op_batch(
                    func,
                    data,
                    args,
                    status_args,
                    batch_size,
                    start,
                    end,
                    this_count,
                    status,
                    is_dict,
                )

        finally:
            if start_and_finish:
                self.status_controller.finish(status)

        return this_count

    def _move_and_modify_dirs(self, library, task):
        """Move files and dirs and modify dirs."""
        changed = self.batch_db_op(
            self.bulk_folders_moved,
            task.dirs_moved,
            ImportStatusTypes.DIRS_MOVED,
            args=(library,),
        )
        task.dirs_moved = None

        changed += self.batch_db_op(
            self.bulk_comics_moved,
            task.files_moved,
            ImportStatusTypes.FILES_MOVED,
            args=(library,),
        )
        task.files_moved = None

        changed += self.batch_db_op(
            self.bulk_folders_modified,
            task.dirs_modified,
            ImportStatusTypes.DIRS_MODIFIED,
            args=(library,),
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

    def _batch_query_one_simple_model(self, fk_field, names, create_fks, status_args):
        """Batch query one simple model name."""
        if fk_field in _CREDIT_FK_NAMES:
            base_cls = Credit
        else:
            base_cls = Comic
        status_args.count += self.batch_db_op(
            self.query_missing_simple_models,
            names,
            ImportStatusTypes.QUERY_MISSING_FKS,
            args=(create_fks, base_cls, fk_field, "name"),
            status_args=status_args,
        )
        if num_names := len(names):
            self.log.info(f"Prepared {num_names} new {fk_field}.")

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
            fks_total = self._get_query_fks_totals(fks)
            status_args = StatusArgs(0, fks_total, time())
            self.status_controller.start(
                ImportStatusTypes.QUERY_MISSING_FKS,
                status_args.count,
                status_args.total,
            )

            if "credits" in fks:
                status_args.count += self.batch_db_op(
                    self.query_missing_credits,
                    fks.pop("credits"),
                    ImportStatusTypes.QUERY_MISSING_FKS,
                    args=(create_credits,),
                    status_args=status_args,
                )
                if num_create_credits := len(create_credits):
                    self.log.info(f"Prepared {num_create_credits} new credits.")

            if "group_trees" in fks:
                for group_class, groups in fks.pop("group_trees").items():
                    status_args.count += self.batch_db_op(
                        self.query_missing_group,
                        groups,
                        ImportStatusTypes.QUERY_MISSING_FKS,
                        args=(group_class, create_groups, update_groups),
                        status_args=status_args,
                    )
                if num_create_groups := len(create_groups):
                    self.log.info(f"Prepared {num_create_groups} new groups.")

            if "comic_paths" in fks:
                status_args.count += self.batch_db_op(
                    self.query_missing_folder_paths,
                    fks.pop("comic_paths"),
                    ImportStatusTypes.QUERY_MISSING_FKS,
                    args=(library.path, create_folder_paths),
                    status_args=status_args,
                )
                if num_create_folder_paths := len(create_folder_paths):
                    self.log.info(f"Prepared {num_create_folder_paths} new folders.")

            for fk_field in sorted(fks.keys()):
                self._batch_query_one_simple_model(
                    fk_field, fks.pop(fk_field), create_fks, status_args
                )
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
            total_fks = self._get_create_fks_totals(
                create_groups,
                update_groups,
                create_folder_paths,
                create_fks,
                create_credits,
            )
            status = ImportStatusTypes.CREATE_FKS
            status_args = StatusArgs(0, total_fks, time())
            self.status_controller.start(status, status_args.count, status_args.total)

            self.log.debug(f"Creating comic foreign keys for {library.path}...")

            self.log.debug(f"Creating {len(create_groups)} groups...")
            for group_class, group_tree_counts in create_groups.items():
                status_args.count += self.batch_db_op(
                    self.bulk_group_creator,
                    group_tree_counts,
                    status,
                    args=(group_class,),
                    status_args=status_args,
                )

            self.log.debug(f"Updating {len(update_groups)} groups...")
            for group_class, group_tree_counts in update_groups.items():
                status_args.count += self.batch_db_op(
                    self.bulk_group_updater,
                    group_tree_counts,
                    status,
                    args=(group_class,),
                    status_args=status_args,
                )

            status_args.count += self.batch_db_op(
                self.bulk_folders_create,
                sorted(create_folder_paths),
                status,
                args=(library,),
                status_args=status_args,
            )

            for named_class, names in create_fks.items():
                status_args.count += self.batch_db_op(
                    self.bulk_create_named_models,
                    names,
                    status,
                    args=(named_class,),
                    status_args=status_args,
                )

            # This must happen after credit_fks created by create_named_models
            status_args.count += self.batch_db_op(
                self.bulk_create_credits,
                create_credits,
                status,
                status_args=status_args,
            )
            return status_args.count
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
            self.bulk_update_comics,
            modified_paths,
            ImportStatusTypes.FILES_MODIFIED,
            args=(library, created_paths, mds),
        )
        if update_count:
            self.log.info(f"Updated {update_count} comics.")

        create_count = self.batch_db_op(
            self.bulk_create_comics,
            created_paths,
            ImportStatusTypes.FILES_CREATED,
            args=(library, mds),
        )
        if create_count:
            self.log.info(f"Created {update_count} comics.")

        linked_count = self.batch_db_op(
            self.bulk_query_and_link_comic_m2m_fields,
            m2m_mds,
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
        created_count = 0
        try:
            update_fis = {}
            create_fis = {}
            delete_fi_paths = set()
            status_args = StatusArgs(0, len(failed_imports), time())
            self.batch_db_op(
                self.query_failed_imports,
                failed_imports,
                ImportStatusTypes.FAILED_IMPORTS,
                args=(library, update_fis, create_fis, delete_fi_paths),
                status_args=status_args,
            )
            status_args.total = len(update_fis) + len(create_fis) + len(delete_fi_paths)

            status_args.count += self.batch_db_op(
                self.bulk_update_failed_imports,
                update_fis,
                ImportStatusTypes.FAILED_IMPORTS,
                args=(library,),
                status_args=status_args,
            )

            created_count = self.batch_db_op(
                self.bulk_create_failed_imports,
                create_fis,
                ImportStatusTypes.FAILED_IMPORTS,
                args=(library,),
                status_args=status_args,
            )
            status_args.count += created_count

            status_args.count += self.batch_db_op(
                self.bulk_cleanup_failed_imports,
                delete_fi_paths,
                ImportStatusTypes.FAILED_IMPORTS,
                args=(library,),
            )
        except Exception as exc:
            self.log.exception(exc)
        return bool(created_count)

    def _delete(self, library, task):
        """Delete files and folders."""
        changed = self.batch_db_op(
            self.bulk_folders_deleted,
            task.dirs_deleted,
            ImportStatusTypes.DIRS_DELETED,
            args=(library,),
        )
        task.dirs_deleted = None
        changed += self.batch_db_op(
            self.bulk_comics_deleted,
            task.files_deleted,
            ImportStatusTypes.FILES_DELETED,
            args=(library,),
        )
        task.files_deleted = None
        return changed

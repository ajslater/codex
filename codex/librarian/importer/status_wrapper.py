"""Wrap jobs in statuses."""
from time import time

from codex.librarian.importer.aggregate_metadata import AggregateMetadataMixin
from codex.librarian.importer.deleted import DeletedMixin
from codex.librarian.importer.failed_imports import FailedImportsMixin
from codex.librarian.importer.moved import MovedMixin
from codex.librarian.importer.status import ImportStatusTypes, StatusArgs
from codex.librarian.importer.update_comics import UpdateComicsMixin
from codex.models import Comic, Credit

_CREDIT_FK_NAMES = ("role", "person")


class StatusWrapperMixin(
    AggregateMetadataMixin,
    DeletedMixin,
    UpdateComicsMixin,
    FailedImportsMixin,
    MovedMixin,
):
    """Methods that are batched."""

    def status_wrapper(
        self, func, data, status, status_args=None, args=None, updates=True
    ):
        """Run a function bracketed by status changes."""
        num_elements = len(data)
        if not num_elements:
            return 0
        if status_args:
            finish = False
        else:
            complete = 0 if updates else None
            status_args = StatusArgs(complete, num_elements, time())
            self.status_controller.start(status, status_args.count, status_args.total)
            finish = True

        if args is None:
            args = ()
        all_args = (data, status_args, *args)
        try:
            count = func(*all_args)
        finally:
            if finish:
                self.status_controller.finish(status)

        return count

    def read_metadata(self, library, all_paths, mds, m2m_mds, fks, fis):
        """Aggregate Metadata."""
        self.status_wrapper(
            self.get_aggregate_metadata,
            all_paths,
            ImportStatusTypes.AGGREGATE_TAGS,
            args=(library, mds, m2m_mds, fks, fis),
        )

    def move_and_modify_dirs(self, library, task):
        """Move files and dirs and modify dirs."""
        changed = 0
        changed += self.status_wrapper(
            self.bulk_folders_moved,
            task.dirs_moved,
            ImportStatusTypes.DIRS_MOVED,
            args=(library,),
        )
        task.dirs_moved = None

        changed += self.status_wrapper(
            self.bulk_comics_moved,
            task.files_moved,
            ImportStatusTypes.FILES_MOVED,
            args=(library,),
        )
        task.files_moved = None

        changed += self.status_wrapper(
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

    def _query_one_simple_model(self, fk_field, names, create_fks, status_args):
        """Batch query one simple model name."""
        if fk_field in _CREDIT_FK_NAMES:
            base_cls = Credit
        else:
            base_cls = Comic
        status_args.count += self.status_wrapper(
            self.query_missing_simple_models,
            names,
            ImportStatusTypes.QUERY_MISSING_FKS,
            args=(create_fks, base_cls, fk_field, "name"),
            status_args=status_args,
        )

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

            status_args.count += self.status_wrapper(
                self.query_missing_credits,
                fks.pop("credits", {}),
                ImportStatusTypes.QUERY_MISSING_FKS,
                args=(create_credits,),
                status_args=status_args,
            )

            for group_class, groups in fks.pop("group_trees", {}).items():
                status_args.count += self.status_wrapper(
                    self.query_missing_group,
                    groups,
                    ImportStatusTypes.QUERY_MISSING_FKS,
                    args=(group_class, create_groups, update_groups),
                    status_args=status_args,
                )

            status_args.count += self.status_wrapper(
                self.query_missing_folder_paths,
                fks.pop("comic_paths", ()),
                ImportStatusTypes.QUERY_MISSING_FKS,
                args=(library.path, create_folder_paths),
                status_args=status_args,
            )

            for fk_field in sorted(fks.keys()):
                self._query_one_simple_model(
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

    def create_all_fks(
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

            for group_class, group_tree_counts in create_groups.items():
                status_args.count += self.status_wrapper(
                    self.bulk_group_creator,
                    group_tree_counts,
                    status,
                    args=(group_class,),
                    status_args=status_args,
                )

            for group_class, group_tree_counts in update_groups.items():
                status_args.count += self.status_wrapper(
                    self.bulk_group_updater,
                    group_tree_counts,
                    status,
                    args=(group_class,),
                    status_args=status_args,
                )

            status_args.count += self.status_wrapper(
                self.bulk_folders_create,
                sorted(create_folder_paths),
                status,
                args=(library,),
                status_args=status_args,
            )

            for named_class, names in create_fks.items():
                status_args.count += self.status_wrapper(
                    self.bulk_create_named_models,
                    names,
                    status,
                    args=(named_class,),
                    status_args=status_args,
                )

            # This must happen after credit_fks created by create_named_models
            status_args.count += self.status_wrapper(
                self.bulk_create_credits,
                create_credits,
                status,
                status_args=status_args,
            )

            return status_args.count
        finally:
            self.status_controller.finish(ImportStatusTypes.CREATE_FKS)

    def create_comic_relations(self, library, fks):
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

        count = self.create_all_fks(
            library,
            create_fks,
            create_groups,
            update_groups,
            create_paths,
            create_credits,
        )
        return count

    def update_create_and_link_comics(
        self, library, modified_paths, created_paths, mds, m2m_mds
    ):
        """Update, create and link comics."""
        imported_count = self.status_wrapper(
            self.bulk_update_comics,
            modified_paths,
            ImportStatusTypes.FILES_MODIFIED,
            args=(library, created_paths, mds),
            updates=False,
        )

        imported_count += self.status_wrapper(
            self.bulk_create_comics,
            created_paths,
            ImportStatusTypes.FILES_CREATED,
            args=(library, mds),
            updates=False,
        )

        self.status_wrapper(
            self.bulk_query_and_link_comic_m2m_fields,
            m2m_mds,
            ImportStatusTypes.LINK_M2M_FIELDS,
        )

        return imported_count

    def fail_imports(self, library, failed_imports):
        """Handle failed imports."""
        created_count = 0
        try:
            update_fis = {}
            create_fis = {}
            delete_fi_paths = set()
            status_args = StatusArgs(0, len(failed_imports), time())
            self.status_wrapper(
                self.query_failed_imports,
                failed_imports,
                ImportStatusTypes.FAILED_IMPORTS,
                args=(library, update_fis, create_fis, delete_fi_paths),
                status_args=status_args,
            )
            status_args.total = len(update_fis) + len(create_fis) + len(delete_fi_paths)

            status_args.count += self.status_wrapper(
                self.bulk_update_failed_imports,
                update_fis,
                ImportStatusTypes.FAILED_IMPORTS,
                args=(library,),
                status_args=status_args,
            )

            created_count = self.status_wrapper(
                self.bulk_create_failed_imports,
                create_fis,
                ImportStatusTypes.FAILED_IMPORTS,
                args=(library,),
                status_args=status_args,
            )
            status_args.count += created_count

            status_args.count += self.status_wrapper(
                self.bulk_cleanup_failed_imports,
                delete_fi_paths,
                ImportStatusTypes.FAILED_IMPORTS,
                args=(library,),
            )
        except Exception as exc:
            self.log.exception(exc)
        return bool(created_count)

    def delete(self, library, task):
        """Delete files and folders."""
        count = self.status_wrapper(
            self.bulk_folders_deleted,
            task.dirs_deleted,
            ImportStatusTypes.DIRS_DELETED,
            args=(library,),
            updates=False,
        )
        task.dirs_deleted = None

        count += self.status_wrapper(
            self.bulk_comics_deleted,
            task.files_deleted,
            ImportStatusTypes.FILES_DELETED,
            args=(library,),
            updates=False,
        )
        task.files_deleted = None
        return count

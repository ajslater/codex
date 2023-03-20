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


class ApplyDBOpsMixin(
    AggregateMetadataMixin,
    DeletedMixin,
    UpdateComicsMixin,
    FailedImportsMixin,
    MovedMixin,
):
    """Apply db ops, wrapped in statuses."""

    def read_metadata(self, library_path, all_paths, mds, m2m_mds, fks, fis):
        """Aggregate Metadata."""
        return self.get_aggregate_metadata(
            all_paths,
            library_path,
            mds,
            m2m_mds,
            fks,
            fis,
        )

    def move_and_modify_dirs(self, library, task):
        """Move files and dirs and modify dirs."""
        changed = 0
        changed += self.bulk_folders_moved(task.dirs_moved, library)
        task.dirs_moved = None

        changed += self.bulk_comics_moved(task.files_moved, library)
        task.files_moved = None

        changed += self.bulk_folders_modified(task.dirs_modified, library)
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
        status_args.count += self.query_missing_simple_models(
            names,
            create_fks,
            base_cls,
            fk_field,
            "name",
            status_args=status_args,
        )

    def query_all_missing_fks(self, library_path, fks):
        """Get objects to create by querying existing objects for the proposed fks."""
        create_credits = set()
        create_groups = {}
        update_groups = {}
        create_folder_paths = set()
        create_fks = {}
        try:
            self.log.debug(
                f"Querying existing foreign keys for comics in {library_path}"
            )
            fks_total = self._get_query_fks_totals(fks)
            status_args = StatusArgs(
                0,
                fks_total,
                time(),
                ImportStatusTypes.QUERY_MISSING_FKS,
            )
            self.status_controller.start(
                status_args.status,
                status_args.count,
                status_args.total,
            )

            status_args.count += self.query_missing_credits(  # type: ignore
                fks.pop("credits", {}),
                create_credits,
                status_args=status_args,
            )

            for group_class, groups in fks.pop("group_trees", {}).items():
                status_args.count += self.query_missing_group(
                    groups,
                    group_class,
                    create_groups,
                    update_groups,
                    status_args=status_args,
                )

            status_args.count += self.query_missing_folder_paths(
                fks.pop("comic_paths", ()),
                library_path,
                create_folder_paths,
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
            status_args = StatusArgs(0, total_fks, time(), ImportStatusTypes.CREATE_FKS)
            self.status_controller.start(
                status_args.status, status_args.count, status_args.total
            )

            for group_class, group_tree_counts in create_groups.items():
                status_args.count += self.bulk_group_creator(  # type: ignore
                    group_tree_counts,
                    group_class,
                    status_args=status_args,
                )

            for group_class, group_tree_counts in update_groups.items():
                status_args.count += self.bulk_group_updater(  # type: ignore
                    group_tree_counts,
                    group_class,
                    status_args=status_args,
                )

            status_args.count += self.bulk_folders_create(  # type: ignore
                sorted(create_folder_paths),
                library,
                status_args=status_args,
            )

            for named_class, names in create_fks.items():
                status_args.count += self.bulk_create_named_models(
                    names,
                    named_class,
                    status_args=status_args,
                )

            # This must happen after credit_fks created by create_named_models
            status_args.count += self.bulk_create_credits(
                create_credits,
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
        ) = self.query_all_missing_fks(library.path, fks)

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
        imported_count = self.bulk_update_comics(
            modified_paths,
            library,
            created_paths,
            mds,
        )
        imported_count += self.bulk_create_comics(created_paths, library, mds)
        self.bulk_query_and_link_comic_m2m_fields(m2m_mds)

        return imported_count

    def fail_imports(self, library, failed_imports):
        """Handle failed imports."""
        created_count = 0
        try:
            update_fis = {}
            create_fis = {}
            delete_fi_paths = set()
            status_args = StatusArgs(
                0,
                len(failed_imports),
                time(),
                ImportStatusTypes.FAILED_IMPORTS,
            )
            self.query_failed_imports(
                failed_imports,
                library,
                update_fis,
                create_fis,
                delete_fi_paths,
                status_args=status_args,
            )
            status_args.total = len(update_fis) + len(create_fis) + len(delete_fi_paths)

            status_args.count += self.bulk_update_failed_imports(  # type: ignore
                update_fis,
                library,
                status_args=status_args,
            )

            created_count = self.bulk_create_failed_imports(
                create_fis,
                library,
                status_args=status_args,
            )
            status_args.count += created_count

            status_args.count += self.bulk_cleanup_failed_imports(
                delete_fi_paths,
                library,
            )
        except Exception as exc:
            self.log.exception(exc)
        return bool(created_count)

    def delete(self, library, task):
        """Delete files and folders."""
        count = self.bulk_folders_deleted(task.dirs_deleted, library)
        task.dirs_deleted = None

        count += self.bulk_comics_deleted(task.files_deleted, library)
        task.files_deleted = None
        return count

"""Wrap jobs in statuses."""
from itertools import chain

from codex.librarian.importer.aggregate_metadata import AggregateMetadataMixin
from codex.librarian.importer.deleted import DeletedMixin
from codex.librarian.importer.failed_imports import FailedImportsMixin
from codex.librarian.importer.moved import MovedMixin
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.importer.update_comics import UpdateComicsMixin
from codex.models import Comic, Creator
from codex.status import Status

_CREATOR_FK_NAMES = ("role", "person")


class ApplyDBOpsMixin(
    AggregateMetadataMixin,
    DeletedMixin,
    UpdateComicsMixin,
    FailedImportsMixin,
    MovedMixin,
):
    """Apply db ops, wrapped in statuses."""

    def read_metadata(self, library_path, all_paths, metadata):
        """Aggregate Metadata."""
        return self.get_aggregate_metadata(all_paths, library_path, metadata)

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

    def _query_one_simple_model(self, fk_field, names, create_fks, status):
        """Batch query one simple model name."""
        base_cls = Creator if fk_field in _CREATOR_FK_NAMES else Comic
        fk_data = create_fks, base_cls, fk_field, "name"
        status.complete += self.query_missing_simple_models(
            names,
            fk_data,
            status=status,
        )

    def query_all_missing_fks(self, library_path, fks):
        """Get objects to create by querying existing objects for the proposed fks."""
        create_creators = set()
        create_groups = {}
        update_groups = {}
        create_folder_paths = set()
        create_fks = {}
        self.log.debug(f"Querying existing foreign keys for comics in {library_path}")
        fks_total = self._get_query_fks_totals(fks)
        status = Status(ImportStatusTypes.QUERY_MISSING_FKS, 0, fks_total)
        try:
            self.status_controller.start(status)

            self.query_missing_creators(  # type: ignore
                fks.pop("creators", {}),
                create_creators,
                status=status,
            )

            create_and_update_groups = {
                "create_groups": create_groups,
                "update_groups": update_groups,
            }
            for group_class, groups in fks.pop("group_trees", {}).items():
                self.query_missing_group(
                    groups,
                    group_class,
                    create_and_update_groups,
                    status=status,
                )

            self.query_missing_folder_paths(
                fks.pop("comic_paths", ()),
                library_path,
                create_folder_paths,
                status=status,
            )

            for fk_field in sorted(fks.keys()):
                self._query_one_simple_model(
                    fk_field, fks.pop(fk_field), create_fks, status
                )
        finally:
            self.status_controller.finish(status)

        return (
            create_groups,
            update_groups,
            create_folder_paths,
            create_fks,
            create_creators,
        )

    @staticmethod
    def _get_create_fks_totals(create_data):
        (
            create_groups,
            update_groups,
            create_folder_paths,
            create_fks,
            create_creators,
        ) = create_data
        total_fks = 0
        for data_group in chain(
            create_groups.values(), update_groups.values(), create_fks.values()
        ):
            total_fks += len(data_group)
        total_fks += len(create_folder_paths) + len(create_creators)
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
            ) = create_data

            for group_class, group_tree_counts in create_groups.items():
                status.complete += self.bulk_group_creator(  # type: ignore
                    group_tree_counts,
                    group_class,
                    status=status,
                )

            for group_class, group_tree_counts in update_groups.items():
                status.complete += self.bulk_group_updater(  # type: ignore
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
                status.complete += self.bulk_create_named_models(
                    names,
                    named_class,
                    status=status,
                )

            # This must happen after creator_fks created by create_named_models
            status.complete += self.bulk_create_creators(
                create_creators,
                status=status,
            )
        finally:
            self.status_controller.finish(status)
        return status.complete

    def create_comic_relations(self, library, fks):
        """Query all foreign keys to determine what needs creating, then create them."""
        if not fks:
            return 0
        create_data = self.query_all_missing_fks(library.path, fks)
        return self.create_all_fks(library, create_data)

    def update_create_and_link_comics(
        self, library, modified_paths, created_paths, metadata
    ):
        """Update, create and link comics."""
        imported_count = self.bulk_update_comics(
            modified_paths,
            library,
            created_paths,
            metadata["mds"],
        )
        imported_count += self.bulk_create_comics(
            created_paths, library, metadata["mds"]
        )
        self.bulk_query_and_link_comic_m2m_fields(metadata["m2m_mds"])

        return imported_count

    def fail_imports(self, library, failed_imports):
        """Handle failed imports."""
        created_count = 0
        try:
            fis = {"update_fis": {}, "create_fis": {}, "delete_fi_paths": set()}
            status = Status(ImportStatusTypes.FAILED_IMPORTS, 0, len(failed_imports))
            status.total = self.query_failed_imports(
                failed_imports,
                library,
                fis,
                status=status,
            )

            self.bulk_update_failed_imports(
                fis["update_fis"],
                library,
                status=status,
            )

            created_count = self.bulk_create_failed_imports(
                fis["create_fis"],
                library,
                status=status,
            )

            self.bulk_cleanup_failed_imports(
                fis["delete_fi_paths"], library, status=status
            )
        except Exception:
            self.log.exception("Processing failed imports")
        return bool(created_count)

    def delete(self, library, task):
        """Delete files and folders."""
        count = self.bulk_folders_deleted(task.dirs_deleted, library)
        task.dirs_deleted = None

        count += self.bulk_comics_deleted(task.files_deleted, library)
        task.files_deleted = None
        return count

"""Update and create failed imports."""

from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.scribe.importer.const import (
    BULK_UPDATE_FAILED_IMPORT_FIELDS,
    CREATE_FIS,
    DELETE_FI_PATHS,
    FIS,
    UPDATE_FIS,
)
from codex.librarian.scribe.importer.delete import DeletedImporter
from codex.librarian.scribe.importer.statii.failed import (
    ImporterFailedImportsCreateStatus,
    ImporterFailedImportsDeleteStatus,
    ImporterFailedImportsQueryStatus,
    ImporterFailedImportsUpdateStatus,
)
from codex.models import Comic, FailedImport


class FailedImportsImporter(DeletedImporter):
    """Methods for failed imports."""

    def _query_failed_import_deletes(self, existing_failed_import_paths, new_fis_paths):
        """Calculate Deletes."""
        untouched_failed_import_paths = existing_failed_import_paths - frozenset(
            new_fis_paths
        )

        succeeded_failed_imports = frozenset(
            Comic.objects.filter(
                library=self.library, path__in=untouched_failed_import_paths
            ).values_list("path", flat=True)
        )

        possibly_missing_failed_import_paths = (
            untouched_failed_import_paths - succeeded_failed_imports
        )
        missing_failed_imports = set()
        for path in possibly_missing_failed_import_paths:
            if not Path(path).is_file():
                missing_failed_imports.add(path)

        return succeeded_failed_imports | missing_failed_imports

    def _query_failed_imports(
        self,
    ) -> tuple[
        ImporterFailedImportsUpdateStatus | None,
        ImporterFailedImportsCreateStatus | None,
        ImporterFailedImportsDeleteStatus | None,
    ]:
        """Determine what to do with failed imports."""
        status = ImporterFailedImportsQueryStatus(0)
        update_status = create_status = delete_status = None
        try:
            self.status_controller.start(status)
            # Calculate creates and updates
            fis = self.metadata.pop(FIS, {})
            existing_failed_import_paths = set(
                FailedImport.objects.filter(library=self.library).values_list(
                    "path", flat=True
                )
            )
            status.total = len(fis) + len(existing_failed_import_paths)
            self.status_controller.update(status)
            self.metadata[UPDATE_FIS] = {}
            self.metadata[CREATE_FIS] = {}
            for path, exc in fis.items():
                if path in existing_failed_import_paths:
                    self.metadata[UPDATE_FIS][path] = exc
                else:
                    self.metadata[CREATE_FIS][path] = exc
                status.increment_complete()
            self.status_controller.update(status)
            if num_update := len(self.metadata[UPDATE_FIS]):
                update_status = ImporterFailedImportsUpdateStatus(0, num_update)
                self.status_controller.update(update_status)
            if num_create := len(self.metadata[CREATE_FIS]):
                create_status = ImporterFailedImportsCreateStatus(0, num_create)
                self.status_controller.update(create_status)

            if DELETE_FI_PATHS not in self.metadata:
                self.metadata[DELETE_FI_PATHS] = set()
            self.metadata[DELETE_FI_PATHS] |= self._query_failed_import_deletes(
                existing_failed_import_paths, fis.keys()
            )
            if num_delete := len(self.metadata[DELETE_FI_PATHS]):
                delete_status = ImporterFailedImportsDeleteStatus(0, num_delete)
                self.status_controller.update(delete_status)
        finally:
            self.status_controller.finish(status, notify=True)
        return update_status, create_status, delete_status

    def _bulk_update_failed_imports(
        self, status: ImporterFailedImportsUpdateStatus | None
    ):
        """Bulk update failed imports."""
        update_failed_imports = self.metadata.pop(UPDATE_FIS, None)
        try:
            if not update_failed_imports:
                return
            if status:
                self.status_controller.start(status)
            update_failed_import_objs = FailedImport.objects.filter(
                library=self.library, path__in=update_failed_imports.keys()
            ).only(*BULK_UPDATE_FAILED_IMPORT_FIELDS)
            if not update_failed_import_objs:
                return
            for fi in update_failed_import_objs:
                try:
                    exc = update_failed_imports.pop(fi.path)
                    fi.set_reason(exc)
                    fi.updated_at = Now()
                    fi.presave()
                except OSError as exc:
                    self.log.warning(f"Presaving failed import {fi.path}: {exc}")
                except Exception:
                    self.log.exception(
                        f"Error preparing failed import update for {fi.path}"
                    )

            FailedImport.objects.bulk_update(
                update_failed_import_objs, fields=BULK_UPDATE_FAILED_IMPORT_FIELDS
            )
            count = len(update_failed_import_objs)
            level = "INFO" if count else "DEBUG"
            self.log.log(level, f"Updated {count} old failed imports.")
        finally:
            self.status_controller.finish(status)

    def _bulk_create_failed_imports(
        self, status: ImporterFailedImportsCreateStatus | None
    ):
        """Bulk create failed imports."""
        create_failed_imports = self.metadata.pop(CREATE_FIS, None)
        try:
            if not create_failed_imports:
                return 0
            if status:
                self.status_controller.start(status)
            create_objs = []
            for path, exc in create_failed_imports.items():
                try:
                    fi = FailedImport(
                        library=self.library, path=path, parent_folder=None
                    )
                    fi.set_reason(exc)
                    create_objs.append(fi)
                    fi.presave()
                except OSError:
                    self.log.warning(
                        f"Error preparing failed import create for {path}: {exc}"
                    )
                except Exception:
                    self.log.exception(
                        f"Error preparing failed import create for {path}"
                    )
            count = len(create_objs)
            if count:
                FailedImport.objects.bulk_create(
                    create_objs,
                    update_conflicts=True,
                    update_fields=BULK_UPDATE_FAILED_IMPORT_FIELDS,
                    unique_fields=FailedImport._meta.unique_together[0],
                )
            level = "INFO" if count else "DEBUG"
            self.log.log(level, f"Added {count} comics to failed imports.")
        finally:
            self.status_controller.finish(status)
        return count

    def _bulk_cleanup_failed_imports(
        self, status: ImporterFailedImportsDeleteStatus | None
    ):
        """Remove FailedImport objects that have since succeeded."""
        delete_failed_imports_paths = self.metadata.pop(DELETE_FI_PATHS, None)
        try:
            if not delete_failed_imports_paths:
                return 0
            if status:
                self.status_controller.start(status)
            # Cleanup FailedImports that were actually successful
            qs = FailedImport.objects.filter(library=self.library).filter(
                path__in=delete_failed_imports_paths
            )
            count, _ = qs.delete()
            level = "INFO" if count else "DEBUG"
            self.log.log(
                level, f"Cleaned up {count} failed imports from {self.library.path}"
            )
            return count
        finally:
            self.status_controller.finish(status)

    def fail_imports(self):
        """Handle failed imports."""
        fis = self.metadata.get(FIS)
        if not fis:
            return
        created_count = 0

        update_status = create_status = delete_status = None
        try:
            update_status, create_status, delete_status = self._query_failed_imports()
            self._bulk_update_failed_imports(update_status)
            created_count += self._bulk_create_failed_imports(create_status)
            self._bulk_cleanup_failed_imports(delete_status)
        except Exception:
            self.log.exception("Processing failed imports")
        finally:
            self.status_controller.finish_many(
                (update_status, create_status, delete_status)
            )
        self.counts.failed_imports = created_count

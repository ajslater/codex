"""Update and create failed imports."""

from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.importer.status import ImportStatusTypes, status_notify
from codex.models import Comic, FailedImport
from codex.status import Status
from codex.threads import QueuedThread

_UPDATE_FIS = "update_fis"
_CREATE_FIS = "create_fis"
_DELETE_FI_PATHS = "delete_fi_paths"
_BULK_UPDATE_FAILED_IMPORT_FIELDS = ("name", "stat", "updated_at")


class FailedImportsMixin(QueuedThread):
    """Methods for failed imports."""

    def _query_failed_import_deletes(
        self, library, failed_imports, existing_failed_import_paths
    ):
        """Calculate Deletes."""
        untouched_failed_import_paths = existing_failed_import_paths - frozenset(
            failed_imports.keys()
        )

        succeeded_failed_imports = frozenset(
            Comic.objects.filter(
                library=library, path__in=untouched_failed_import_paths
            ).values_list("path", flat=True)
        )

        possibly_missing_failed_import_paths = (
            untouched_failed_import_paths - succeeded_failed_imports
        )
        missing_failed_imports = set()
        for path in possibly_missing_failed_import_paths:
            if not Path(path).exists():
                missing_failed_imports.add(path)

        return succeeded_failed_imports | missing_failed_imports

    @status_notify()
    def _query_failed_imports(
        self,
        failed_imports,
        library,
        fis,
        **kwargs,
    ):
        """Determine what to do with failed imports."""
        if not failed_imports:
            return 0

        # Remove the files deleted hack thing.
        failed_imports.pop("files_deleted", None)

        existing_failed_import_paths = set(
            FailedImport.objects.filter(library=library).values_list("path", flat=True)
        )

        # Calculate creates and updates
        for path, exc in failed_imports.items():
            if path in existing_failed_import_paths:
                fis[_UPDATE_FIS][path] = exc
            else:
                fis[_CREATE_FIS][path] = exc

        fis[_DELETE_FI_PATHS] |= self._query_failed_import_deletes(
            library, failed_imports, existing_failed_import_paths
        )

        count = 0
        for iterable in fis.values():
            count += len(iterable)
        return count

    @status_notify()
    def _bulk_update_failed_imports(
        self, update_failed_imports, library, **kwargs
    ) -> int:
        """Bulk update failed imports."""
        if not update_failed_imports:
            return 0
        update_failed_import_objs = FailedImport.objects.filter(
            library=library, path__in=update_failed_imports.keys()
        ).only(*_BULK_UPDATE_FAILED_IMPORT_FIELDS)
        if not update_failed_import_objs:
            return 0
        now = Now()
        for fi in update_failed_import_objs:
            try:
                exc = update_failed_imports.pop(fi.path)
                fi.set_reason(exc)
                fi.set_stat()
                fi.updated_at = now
            except Exception as exc:
                self.log.exception(
                    f"Error preparing failed import update for {fi.path}"
                )

        FailedImport.objects.bulk_update(
            update_failed_import_objs, fields=_BULK_UPDATE_FAILED_IMPORT_FIELDS
        )
        count = len(update_failed_import_objs)
        if count:
            self.log.info(f"Updated {count} old failed imports.")
        return count

    @status_notify()
    def _bulk_create_failed_imports(self, create_failed_imports, library, **kwargs):
        """Bulk create failed imports."""
        if not create_failed_imports:
            return 0
        create_objs = []
        for path, exc in create_failed_imports.items():
            try:
                fi = FailedImport(library=library, path=path, parent_folder=None)
                fi.set_reason(exc)
                fi.set_stat()
                create_objs.append(fi)
            except Exception as exc:
                self.log.exception(f"Error preparing failed import create for {path}")
        FailedImport.objects.bulk_create(
            create_objs,
            update_conflicts=True,
            update_fields=_BULK_UPDATE_FAILED_IMPORT_FIELDS,
            unique_fields=FailedImport._meta.unique_together[0],  # type: ignore
        )
        count = len(create_objs)
        if count:
            self.log.info(f"Added {count} comics to failed imports.")
        return count

    @status_notify()
    def _bulk_cleanup_failed_imports(
        self, delete_failed_imports_paths, library, **kwargs
    ):
        """Remove FailedImport objects that have since succeeded."""
        if not delete_failed_imports_paths:
            return 0
        # Cleanup FailedImports that were actually successful
        qs = FailedImport.objects.filter(library=library).filter(
            path__in=delete_failed_imports_paths
        )
        qs.delete()
        count = len(delete_failed_imports_paths)
        if count:
            self.log.info(f"Cleaned up {count} failed imports from {library.path}")
        return count

    def fail_imports(self, library, failed_imports, is_files_deleted):
        """Handle failed imports."""
        created_count = 0
        try:
            fis = {_UPDATE_FIS: {}, _CREATE_FIS: {}, _DELETE_FI_PATHS: set()}
            if is_files_deleted:
                # if any files were deleted. Run the failed import check
                failed_imports["files_deleted"] = True
            status = Status(ImportStatusTypes.FAILED_IMPORTS, 0, len(failed_imports))
            status.total = self._query_failed_imports(
                failed_imports,
                library,
                fis,
                status=status,
            )

            self._bulk_update_failed_imports(
                fis[_UPDATE_FIS],
                library,
                status=status,
            )

            created_count = self._bulk_create_failed_imports(
                fis[_CREATE_FIS],
                library,
                status=status,
            )

            self._bulk_cleanup_failed_imports(
                fis[_DELETE_FI_PATHS], library, status=status
            )
        except Exception:
            self.log.exception("Processing failed imports")
        return bool(created_count)

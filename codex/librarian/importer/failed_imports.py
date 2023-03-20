"""Update and create failed imports."""
from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.importer.status import status
from codex.models import FailedImport
from codex.threads import QueuedThread

_BULK_UPDATE_FAILED_IMPORT_FIELDS = ("name", "stat", "updated_at")


class FailedImportsMixin(QueuedThread):
    """Methods for failed imports."""

    @status()
    def query_failed_imports(
        self,
        failed_imports,
        library,
        update_failed_imports,
        create_failed_imports,
        delete_failed_import_paths,
        status_args=None,
    ):
        """Determine what to do with failed imports."""
        if not failed_imports:
            return 0

        existing_failed_import_paths = set(
            FailedImport.objects.filter(library=library).values_list("path", flat=True)
        )

        # Calculate creates and updates
        for path, exc in failed_imports.items():
            if path in existing_failed_import_paths:
                update_failed_imports[path] = exc
            else:
                create_failed_imports[path] = exc

        # Calculate Deletes
        untouched_failed_import_paths = existing_failed_import_paths - set(
            failed_imports.keys()
        )

        possibly_succeeed_failed_import_paths = set()
        succeeded_failed_imports = set(
            FailedImport.objects.filter(
                library=library, path__in=possibly_succeeed_failed_import_paths
            ).values_list("path", flat=True)
        )

        possibly_missing_failed_import_paths = (
            untouched_failed_import_paths - succeeded_failed_imports
        )

        missing_failed_imports = set()
        for path in possibly_missing_failed_import_paths:
            if not Path(path).exists():
                missing_failed_imports.add(path)

        delete_failed_import_paths |= succeeded_failed_imports | missing_failed_imports
        return (
            len(update_failed_imports)
            + len(create_failed_imports)
            + len(delete_failed_import_paths)
        )

    @status()
    def bulk_update_failed_imports(
        self, update_failed_imports, library, status_args=None
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
                self.log.error(f"Error preparing failed import update for {fi.path}")
                self.log.exception(exc)

        FailedImport.objects.bulk_update(
            update_failed_import_objs, fields=_BULK_UPDATE_FAILED_IMPORT_FIELDS
        )
        count = len(update_failed_import_objs)
        if count:
            self.log.info(f"Updated {count} old failed imports.")
        return count

    @status()
    def bulk_create_failed_imports(
        self, create_failed_imports, library, status_args=None
    ):
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
                self.log.error(f"Error preparing failed import create for {path}")
                self.log.exception(exc)
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

    @status()
    def bulk_cleanup_failed_imports(
        self, delete_failed_imports_paths, library, status_args=None
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
        self.log.info(f"Cleaned up {count} failed imports from {library.path}")
        return count

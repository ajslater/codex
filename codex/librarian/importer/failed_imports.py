"""Update and create failed imports."""
import logging
from pathlib import Path

from django.db.models.functions import Now

from codex.models import FailedImport
from codex.threads import QueuedThread

_BULK_UPDATE_FAILED_IMPORT_FIELDS = ("name", "stat", "updated_at")


class FailedImportsMixin(QueuedThread):
    """Methods for failed imports."""

    def query_failed_imports(
        self,
        library,
        failed_imports,
        count,
        _total,
        _since,
        update_failed_imports,
        create_failed_imports,
        delete_failed_import_paths,
    ):
        """Determine what to do with failed imports."""
        update_failed_imports = {}
        create_failed_imports = {}
        delete_failed_import_paths = set()
        if not failed_imports:
            return count

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
            count
            + len(update_failed_imports)
            + len(create_failed_imports)
            + len(delete_failed_import_paths)
        )

    def bulk_update_failed_imports(
        self, library, update_failed_imports, count, _total, _since
    ):
        """Bulk update failed imports."""
        if not update_failed_imports:
            return
        update_failed_import_objs = FailedImport.objects.filter(
            library=library, path__in=update_failed_imports.keys()
        ).only(*_BULK_UPDATE_FAILED_IMPORT_FIELDS)
        if not update_failed_imports:
            return count
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

        count += FailedImport.objects.bulk_update(
            update_failed_import_objs, fields=_BULK_UPDATE_FAILED_IMPORT_FIELDS
        )
        if count:
            level = logging.INFO
        else:
            level = logging.DEBUG
        self.log.log(level, f"Updated {count} old failed imports.")
        return count

    def bulk_create_failed_imports(self, library, create_failed_imports, count, _total):
        """Bulk create failed imports."""
        if not create_failed_imports:
            return False
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
        if create_objs:
            created_objs = FailedImport.objects.bulk_create(
                create_objs,
                update_conflicts=True,
                update_fields=_BULK_UPDATE_FAILED_IMPORT_FIELDS,
                unique_fields=FailedImport._meta.unique_together[0],
            )
            count += len(created_objs)
            if count:
                level = logging.INFO
            else:
                level = logging.DEBUG
            self.log.log(level, f"Added {count} comics to failed imports.")
        return count

    def bulk_cleanup_failed_imports(
        self, library, delete_failed_imports_paths, count, _total, _since
    ):
        """Remove FailedImport objects that have since succeeded."""
        # Cleanup FailedImports that were actually successful
        qs = FailedImport.objects.filter(library=library).filter(
            path__in=delete_failed_imports_paths
        )
        qs.delete()
        count += len(delete_failed_imports_paths)
        if count:
            self.log.info(f"Cleaned up {count} failed imports from {library.path}")
        else:
            self.log.debug("No failed imports to clean up.")
        return count

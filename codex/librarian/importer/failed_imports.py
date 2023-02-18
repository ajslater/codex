"""Update and create failed imports."""
import logging
from pathlib import Path

from django.db.models import Q
from django.db.models.functions import Now

from codex.librarian.importer.status import ImportStatusTypes
from codex.models import Comic, FailedImport
from codex.threads import QueuedThread

_BULK_UPDATE_FAILED_IMPORT_FIELDS = ("name", "stat", "updated_at")


class FailedImportsMixin(QueuedThread):
    """Methods for failed imports."""

    def _bulk_update_failed_imports(self, library, failed_imports):
        """Bulk update failed imports."""
        if not failed_imports:
            return
        update_failed_imports = FailedImport.objects.filter(
            library=library, path__in=failed_imports.keys()
        )

        count = 0
        now = Now()
        for fi in update_failed_imports:
            try:
                exc = failed_imports.pop(fi.path)
                fi.set_reason(exc)
                fi.set_stat()
                fi.updated_at = now
            except Exception as exc:
                self.log.error(f"Error preparing failed import update for {fi.path}")
                self.log.exception(exc)

        if update_failed_imports:
            count = FailedImport.objects.bulk_update(
                update_failed_imports, fields=_BULK_UPDATE_FAILED_IMPORT_FIELDS
            )
        if count is None:
            count = 0
        if count:
            level = logging.INFO
        else:
            level = logging.DEBUG
        self.log.log(level, f"Updated {count} old comics in failed imports.")

    def _bulk_create_failed_imports(self, library, failed_imports) -> bool:
        """Bulk create failed imports."""
        try:
            if not failed_imports:
                return False
            create_failed_imports = []
            for path, exc in failed_imports.items():
                try:
                    fi = FailedImport(library=library, path=path, parent_folder=None)
                    fi.set_reason(exc)
                    fi.set_stat()
                    create_failed_imports.append(fi)
                except Exception as exc:
                    self.log.error(f"Error preparing failed import create for {path}")
                    self.log.exception(exc)
            if create_failed_imports:
                FailedImport.objects.bulk_create(create_failed_imports)
            count = len(create_failed_imports)
            if count:
                level = logging.INFO
            else:
                level = logging.DEBUG
            self.log.log(level, f"Added {count} comics to failed imports.")
            return bool(count)
        finally:
            self.status_controller.finish(ImportStatusTypes.CREATE_FAILED_IMPORTS)

    def _bulk_cleanup_failed_imports(self, library):
        """Remove FailedImport objects that have since succeeded."""
        try:
            self.status_controller.start(ImportStatusTypes.CLEAN_FAILED_IMPORTS)
            self.log.debug("Cleaning up failed imports...")
            failed_import_paths = FailedImport.objects.filter(
                library=library
            ).values_list("path", flat=True)

            # Cleanup FailedImports that were actually successful
            succeeded_imports = Comic.objects.filter(
                library=library, path__in=failed_import_paths
            ).values_list("path", flat=True)

            # Cleanup FailedImports that aren't on the filesystem anymore.
            didnt_succeed_paths = (
                FailedImport.objects.filter(library=library)
                .exclude(path__in=succeeded_imports)
                .values_list("path", flat=True)
            )
            missing_failed_imports = set()
            for path in didnt_succeed_paths:
                if not Path(path).exists():
                    missing_failed_imports.add(path)

            count, _ = (
                FailedImport.objects.filter(library=library.pk)
                .filter(
                    Q(path__in=succeeded_imports) | Q(path__in=missing_failed_imports)
                )
                .delete()
            )
            if count:
                self.log.info(f"Cleaned up {count} failed imports from {library.path}")
            else:
                self.log.debug("No failed imports to clean up.")
        finally:
            self.status_controller.finish(ImportStatusTypes.CLEAN_FAILED_IMPORTS)

    def bulk_fail_imports(self, library, failed_imports) -> bool:
        """Handle failed imports."""
        new_failed_imports = False
        try:
            self._bulk_update_failed_imports(library, failed_imports)
            new_failed_imports = self._bulk_create_failed_imports(
                library, failed_imports
            )
            self._bulk_cleanup_failed_imports(library)
        except Exception as exc:
            self.log.exception(exc)
        return new_failed_imports

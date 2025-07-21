"""Update and create failed imports."""

from codex.librarian.scribe.importer.const import DELETE_FI_PATHS
from codex.librarian.scribe.importer.failed.create import (
    FailedImportsCreateUpdateImporter,
)
from codex.librarian.scribe.importer.statii.failed import (
    ImporterFailedImportsDeleteStatus,
)
from codex.models import FailedImport


class FailedImportsImporter(FailedImportsCreateUpdateImporter):
    """Methods for failed imports."""

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

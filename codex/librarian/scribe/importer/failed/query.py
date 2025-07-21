"""Update and create failed imports."""

from pathlib import Path

from codex.librarian.scribe.importer.const import (
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


class FailedImportsQueryImporter(DeletedImporter):
    """Methods for failed imports."""

    def _query_failed_import_deletes(self, existing_failed_import_paths, new_fis_paths):
        """Calculate Deletes."""
        untouched_failed_import_paths = existing_failed_import_paths - frozenset(
            new_fis_paths
        )

        qs = Comic.objects.filter(
            library=self.library, path__in=untouched_failed_import_paths
        ).only("path")
        succeeded_failed_imports = frozenset(qs.values_list("path", flat=True))

        possibly_missing_failed_import_paths = (
            untouched_failed_import_paths - succeeded_failed_imports
        )
        missing_failed_import_paths = set()
        for path in possibly_missing_failed_import_paths:
            name = path.casefold()
            # Case sensitive matching. exists() and is_file() are case insensitive.
            # This will fail if there is a parent directory case mismatch.
            # Rather than do a recursive solution, add it to missing if it fails.
            try:
                for path_obj in Path(path).parent.iterdir():
                    if path_obj.name.casefold() == name:
                        break
                else:
                    missing_failed_import_paths.add(path)
            except FileNotFoundError:
                missing_failed_import_paths.add(path)

        return succeeded_failed_imports | missing_failed_import_paths

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
            status.increment_complete(len(existing_failed_import_paths))
            if num_delete := len(self.metadata[DELETE_FI_PATHS]):
                delete_status = ImporterFailedImportsDeleteStatus(0, num_delete)
                self.status_controller.update(delete_status)
        finally:
            self.status_controller.finish(status, notify=True)
        return update_status, create_status, delete_status

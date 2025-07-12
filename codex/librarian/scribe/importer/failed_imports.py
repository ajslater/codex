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
from codex.librarian.scribe.importer.status import ImporterFailedImportsStatus
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

    def _query_failed_imports(self):
        """Determine what to do with failed imports."""
        existing_failed_import_paths = set(
            FailedImport.objects.filter(library=self.library).values_list(
                "path", flat=True
            )
        )

        # Calculate creates and updates
        fis = self.metadata.pop(FIS, {})
        self.metadata[UPDATE_FIS] = {}
        self.metadata[CREATE_FIS] = {}
        for path, exc in fis.items():
            if path in existing_failed_import_paths:
                self.metadata[UPDATE_FIS][path] = exc
            else:
                self.metadata[CREATE_FIS][path] = exc

        if DELETE_FI_PATHS not in self.metadata:
            self.metadata[DELETE_FI_PATHS] = set()
        self.metadata[DELETE_FI_PATHS] |= self._query_failed_import_deletes(
            existing_failed_import_paths, fis.keys()
        )

    def _bulk_update_failed_imports(self):
        """Bulk update failed imports."""
        update_failed_imports = self.metadata.pop(UPDATE_FIS, None)
        if not update_failed_imports:
            return
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
        return

    def _bulk_create_failed_imports(self):
        """Bulk create failed imports."""
        create_failed_imports = self.metadata.pop(CREATE_FIS, None)
        if not create_failed_imports:
            return 0
        create_objs = []
        for path, exc in create_failed_imports.items():
            try:
                fi = FailedImport(library=self.library, path=path, parent_folder=None)
                fi.set_reason(exc)
                create_objs.append(fi)
                fi.presave()
            except OSError:
                self.log.warning(
                    f"Error preparing failed import create for {path}: {exc}"
                )
            except Exception:
                self.log.exception(f"Error preparing failed import create for {path}")
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
        return count

    def _bulk_cleanup_failed_imports(self):
        """Remove FailedImport objects that have since succeeded."""
        delete_failed_imports_paths = self.metadata.pop(DELETE_FI_PATHS, None)
        if not delete_failed_imports_paths:
            return 0
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

    def fail_imports(self):
        """Handle failed imports."""
        fis = self.metadata.get(FIS)
        if not fis:
            return
        status = ImporterFailedImportsStatus()
        self.status_controller.start(status)
        created_count = 0

        try:
            self._query_failed_imports()
            self._bulk_update_failed_imports()
            created_count += self._bulk_create_failed_imports()
            self._bulk_cleanup_failed_imports()
        except Exception:
            self.log.exception("Processing failed imports")
        self.status_controller.finish(status)
        self.counts.failed_imports = created_count

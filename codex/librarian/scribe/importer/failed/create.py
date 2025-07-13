"""Update and create failed imports."""

from django.db.models.functions import Now

from codex.librarian.scribe.importer.const import (
    BULK_UPDATE_FAILED_IMPORT_FIELDS,
    CREATE_FIS,
    UPDATE_FIS,
)
from codex.librarian.scribe.importer.failed.query import FailedImportsQueryImporter
from codex.librarian.scribe.importer.statii.failed import (
    ImporterFailedImportsCreateStatus,
    ImporterFailedImportsUpdateStatus,
)
from codex.models import FailedImport


class FailedImportsCreateUpdateImporter(FailedImportsQueryImporter):
    """Methods for failed imports."""

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

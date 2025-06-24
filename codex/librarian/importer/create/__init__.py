"""
Create all missing comic foreign keys for an import.

So we may safely create the comics next.
"""

from codex.librarian.importer.const import (
    CREATE_FKS,
    TOTAL,
    UPDATE_FKS,
)
from codex.librarian.importer.create.foreign_keys import (
    CreateForeignKeysCreateUpdateImporter,
)
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.status import Status
from codex.models.groups import Folder


class CreateForeignKeysImporter(CreateForeignKeysCreateUpdateImporter):
    """Methods for creating foreign keys."""

    def create_all_fks(self) -> int:
        """Bulk create all foreign keys."""
        count = 0
        fkc = self.metadata.get(CREATE_FKS, {})
        create_status = Status(ImportStatusTypes.CREATE_TAGS, 0, fkc.pop(TOTAL, 0))
        try:
            if not fkc:
                return count
            self.status_controller.start(create_status)
            count += self.bulk_folders_create(
                fkc.pop(Folder, frozenset()), create_status
            )
            count += self.bulk_create_all_models(create_status)
        finally:
            self.metadata.pop(CREATE_FKS, None)
            self.status_controller.finish(create_status)
        return count

    def update_all_fks(self) -> int:
        """Bulk update all foreign keys."""
        count = 0
        fku = self.metadata.get(UPDATE_FKS, {})
        update_status = Status(ImportStatusTypes.UPDATE_TAGS, 0, fku.pop(TOTAL, 0))
        try:
            if not fku:
                return count
            self.status_controller.start(update_status)
            count += self.bulk_folders_update(
                fku.pop(Folder, frozenset()), update_status
            )
            count += self.bulk_update_all_models(update_status)
        finally:
            self.metadata.pop(UPDATE_FKS, None)
            self.status_controller.finish(update_status)
        return count

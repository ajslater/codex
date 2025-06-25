"""
Create all missing comic foreign keys for an import.

So we may safely create the comics next.
"""

from codex.librarian.scribe.importer.const import (
    CREATE_FKS,
    TOTAL,
    UPDATE_FKS,
)
from codex.librarian.scribe.importer.create.foreign_keys import (
    CreateForeignKeysCreateUpdateImporter,
)
from codex.librarian.scribe.status import ScribeStatusTypes
from codex.librarian.status import Status
from codex.models.groups import Folder


class CreateForeignKeysImporter(CreateForeignKeysCreateUpdateImporter):
    """Methods for creating foreign keys."""

    def create_all_fks(self) -> int:
        """Bulk create all foreign keys."""
        count = 0
        fkc = self.metadata.get(CREATE_FKS, {})
        create_status = Status(ScribeStatusTypes.CREATE_TAGS, 0, fkc.pop(TOTAL, 0))
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
        update_status = Status(ScribeStatusTypes.UPDATE_TAGS, 0, fku.pop(TOTAL, 0))
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

    def create_and_update(self):
        """Create and update FKs, covers and comics."""
        fk_count = self.create_all_fks()
        fk_count += self.update_all_fks()
        self.counts.tags = fk_count

        cover_count = self.create_custom_covers()
        cover_count += self.update_custom_covers()
        self.counts.covers = cover_count

        comic_count = self.update_comics()
        comic_count += self.create_comics()
        self.counts.comic = comic_count

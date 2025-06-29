"""
Create all missing comic foreign keys for an import.

So we may safely create the comics next.
"""

from codex.librarian.scribe.importer.create.foreign_keys import (
    CreateForeignKeysCreateUpdateImporter,
)


class CreateForeignKeysImporter(CreateForeignKeysCreateUpdateImporter):
    """Methods for creating foreign keys."""

    def create_and_update(self):
        """Create and update FKs, covers and comics."""
        if self.abort_event.is_set():
            return
        fk_count = self.create_all_fks()
        if self.abort_event.is_set():
            return
        fk_count += self.update_all_fks()
        self.counts.tags = fk_count
        if self.abort_event.is_set():
            return

        cover_count = self.create_custom_covers()
        if self.abort_event.is_set():
            return
        cover_count += self.update_custom_covers()
        self.counts.covers = cover_count

        if self.abort_event.is_set():
            return
        comic_count = self.update_comics()
        comic_count += self.create_comics()
        self.counts.comic = comic_count

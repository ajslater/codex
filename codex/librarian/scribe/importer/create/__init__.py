"""
Create all missing comic many to many objects for an import.

So we may safely create the comics next.
"""

from django.db import transaction

from codex.librarian.scribe.importer.create.foreign_keys import (
    CreateForeignKeysCreateUpdateImporter,
)


class CreateForeignKeysImporter(CreateForeignKeysCreateUpdateImporter):
    """Methods for creating foreign keys."""

    def create_and_update(self) -> None:
        """
        Create and update FKs, covers and comics.

        Wrapped in ``transaction.atomic`` to coalesce the ~2000+
        bulk_create / bulk_update commits this phase generates into
        one fsync. The codex daemon already serializes writers via
        ``db_write_lock``, so the long write transaction does not
        starve other writers; readers under WAL never block on a
        writer regardless of transaction length.
        """
        if self.abort_event.is_set():
            return
        with transaction.atomic():
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

"""
Create all missing comic many to many objects for an import.

So we may safely create the comics next.
"""

from codex.librarian.scribe.importer.create.foreign_keys import (
    CreateForeignKeysCreateUpdateImporter,
)


class CreateForeignKeysImporter(CreateForeignKeysCreateUpdateImporter):
    """Methods for creating foreign keys."""

    def create_and_update(self) -> None:
        """
        Create and update FKs, covers and comics.

        The previous version wrapped the body in ``transaction.atomic``
        to coalesce the ~2000+ ``bulk_create`` / ``bulk_update`` commits
        this phase generates into a single fsync. That coalescing was a
        no-op in practice with the current ``importer_pragmas``
        (``synchronous=NORMAL`` + ``wal_autocheckpoint=0``) — every
        commit is a WAL frame append with no fsync until the post-
        import ``wal_checkpoint(TRUNCATE)`` — and it had a real
        downside: ``status_controller.start`` / ``update`` / ``finish``
        writes lived in the same transaction, so readers (admin status
        API, websocket-poller) couldn't see them until commit. By the
        time the multi-minute create-and-update transaction committed,
        ``finish()`` had already cleared each row, and the
        Create Tags / Update Tags / Create Comics / Update Comics
        spinners never appeared during the actual work.

        Without the wrapper each helper's bulk operation runs in
        Django's per-statement autocommit. Each ``start`` / ``update``
        / ``finish`` lands in its own transaction and is visible to
        readers immediately.

        Counts use ``+=`` so a chunked apply() loop can call
        ``create_and_update`` once per chunk and still report a
        correct total at finish.
        """
        if self.abort_event.is_set():
            return
        fk_count = self.create_all_fks()
        if self.abort_event.is_set():
            return
        fk_count += self.update_all_fks()
        self.counts.tags += fk_count
        if self.abort_event.is_set():
            return

        cover_count = self.create_custom_covers()
        if self.abort_event.is_set():
            return
        cover_count += self.update_custom_covers()
        self.counts.covers += cover_count

        if self.abort_event.is_set():
            return
        comic_count = self.update_comics()
        comic_count += self.create_comics()
        self.counts.comic += comic_count

"""Clean up the database after moves or imports."""

from codex.librarian.scribe.importer.delete.folders import DeletedFoldersImporter
from codex.librarian.scribe.timestamp_update import TimestampUpdater


class DeletedImporter(DeletedFoldersImporter):
    """Delete database objects methods."""

    def delete(self) -> None:
        """Delete files and folders."""
        if self.abort_event.is_set():
            return
        folders_deleted, comics_cascaded, folder_collections = (
            self.bulk_folders_deleted()
        )
        self.counts.folders_deleted += folders_deleted
        # Comics under a deleted folder die by cascade, not by path, so they
        # never reach ``bulk_comics_deleted`` to be counted there.
        self.counts.comics_deleted += comics_cascaded
        if self.abort_event.is_set():
            return
        comics_deleted, deleted_comic_collections = self.bulk_comics_deleted()
        self.counts.comics_deleted += comics_deleted
        for model, pks in folder_collections.items():
            if pks:
                deleted_comic_collections.setdefault(model, set()).update(pks)
        if self.abort_event.is_set():
            return
        self.counts.covers_deleted = self.bulk_covers_deleted()
        if self.abort_event.is_set():
            return
        # Fold in collections comics moved OUT of during updates (FK changes).
        # ``bulk_comics_deleted`` only captures collections of *deleted* comics,
        # so without this a move (e.g. a publisher-name edit) re-stamps only the
        # destination collection and the source view never refreshes.
        for model, pks in self.moved_source_collections.items():
            if pks:
                deleted_comic_collections.setdefault(model, set()).update(pks)
        timestamp_updater = TimestampUpdater(
            self.log, self.librarian_queue, self.db_write_lock
        )
        timestamp_updater.update_library_collections(
            self.library, self.start_time, deleted_comic_collections
        )

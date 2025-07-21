"""Clean up the database after moves or imports."""

from codex.librarian.scribe.importer.delete.folders import DeletedFoldersImporter
from codex.librarian.scribe.timestamp_update import TimestampUpdater


class DeletedImporter(DeletedFoldersImporter):
    """Delete database objects methods."""

    def delete(self):
        """Delete files and folders."""
        if self.abort_event.is_set():
            return
        self.counts.folders_deleted += self.bulk_folders_deleted()
        if self.abort_event.is_set():
            return
        self.counts.comics_deleted, deleted_comic_groups = self.bulk_comics_deleted()
        if self.abort_event.is_set():
            return
        self.counts.covers_deleted = self.bulk_covers_deleted()
        if self.abort_event.is_set():
            return
        timestamp_updater = TimestampUpdater(
            self.log, self.librarian_queue, self.db_write_lock
        )
        timestamp_updater.update_library_groups(
            self.library, self.start_time, deleted_comic_groups
        )

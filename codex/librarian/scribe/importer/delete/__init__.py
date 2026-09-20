"""Clean up the database after moves or imports."""

from codex.librarian.scribe.importer.delete.existence import (
    SECOND_LOOK_DELAY_S,
    revived_paths,
)
from codex.librarian.scribe.importer.delete.folders import DeletedFoldersImporter
from codex.librarian.scribe.timestamp_update import TimestampUpdater

#: Revived paths named in the second look's warning.
_REVIVED_EXAMPLES = 3


class DeletedImporter(DeletedFoldersImporter):
    """Delete database objects methods."""

    def _second_look(self) -> None:
        """
        Drop deletes that answer on a second probe. One wait per batch.

        Both scanners infer deletes from a single observation, and a
        share that drops for a few seconds answers exactly like one that
        lost a file. Looking twice costs one wait per batch that carries
        deletes, and nothing at all when a scan found none.

        Covers are excluded: they never come from a scan, so there is no
        filesystem race to lose.
        """
        candidates = self.task.dirs_deleted | self.task.files_deleted
        if not candidates:
            return
        revived = revived_paths(candidates, self.abort_event.wait)
        if not revived:
            return
        examples = ", ".join(sorted(revived)[:_REVIVED_EXAMPLES])
        reason = (
            f"Not deleting {len(revived)} paths a scan reported missing that"
            f" answered {SECOND_LOOK_DELAY_S}s later; the filesystem may be"
            f" flapping: {examples}..."
        )
        self.log.warning(reason)
        self.task.dirs_deleted -= revived
        self.task.files_deleted -= revived

    def delete(self) -> None:
        """Delete files and folders."""
        if self.abort_event.is_set():
            return
        self._second_look()
        if self.abort_event.is_set():
            # An abort during the wait returns from it early.
            return
        folders_deleted, comics_cascaded, folder_collections = (
            self.bulk_folders_deleted()
        )
        self.counts.folders_deleted += folders_deleted
        # Comics under a deleted folder die by cascade, not by path, so they
        # never reach ``bulk_comics_deleted`` to be counted there.
        # ``bulk_folders_deleted`` probes and counts them itself.
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

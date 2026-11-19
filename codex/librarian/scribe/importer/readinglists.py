"""
Bring reading lists in step with an import.

The lists from story-arc tags sync with the tags, and when the import added
comics, every list with missing issues is matched again on the scribe
after this import.
"""

from codex.librarian.notifier.tasks import READING_LISTS_CHANGED_TASK
from codex.librarian.scribe.importer.moved import MovedImporter
from codex.librarian.scribe.readinglists.status import ReadingListSyncStatus
from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.librarian.scribe.readinglists.tasks import ReadingListRematchTask

# Counters that mean a comic's story-arc links may have changed. Moves,
# covers, pending deletes and revivals keep every link as it was.
_ARC_LINK_COUNTERS = (
    "comic",
    "tags",
    "link",
    "comics_deleted",
    "folders_deleted",
    "tags_deleted",
)


class ReadingListsImporter(MovedImporter):
    """Sync the reading lists from tags."""

    def _arc_links_may_have_changed(self) -> bool:
        return any(getattr(self.counts, name) for name in _ARC_LINK_COUNTERS)

    def _queue_rematch(self) -> None:
        """Match lists again: a comic this import added may be one they miss."""
        if self.counts.comic:
            self.librarian_queue.put(ReadingListRematchTask())

    def sync_reading_lists(self) -> None:
        """Bring the lists from story-arc tags in step with this import."""
        self._queue_rematch()
        if not self._arc_links_may_have_changed():
            return
        status = ReadingListSyncStatus()
        self.status_controller.start(status)
        try:
            counts = sync_tag_lists()
            status.complete = counts.changed
            if counts.changed:
                self.log.info(f"Reading lists from tags: {counts}.")
                self.librarian_queue.put(READING_LISTS_CHANGED_TASK)
        finally:
            self.status_controller.finish(status)

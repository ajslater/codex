"""
Bring reading lists in step with an import.

The lists from story-arc tags sync with the tags, then lists holding a
whole series, folder or list sync their comics. When the import added
comics, every list with missing issues is matched again on the scribe
after this import.
"""

from codex.librarian.notifier.tasks import READING_LISTS_CHANGED_TASK
from codex.librarian.scribe.importer.moved import MovedImporter
from codex.librarian.scribe.readinglists.live import sync_live
from codex.librarian.scribe.readinglists.status import (
    ReadingListLiveStatus,
    ReadingListSyncStatus,
)
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


# Counters that mean a collection's comics may have changed: a comic made
# or moved to another series, folder links, tag lists that lists hold, and
# comics or folders gone. A revived comic kept its row and links.
_LIVE_COUNTERS = (
    "comic",
    "link",
    "tags",
    "comics_moved",
    "folders_moved",
    "comics_deleted",
    "folders_deleted",
)


class ReadingListsImporter(MovedImporter):
    """Sync the reading lists from tags."""

    def _arc_links_may_have_changed(self) -> bool:
        return any(getattr(self.counts, name) for name in _ARC_LINK_COUNTERS)

    def _queue_rematch(self) -> None:
        """Match lists again: a comic this import added may be one they miss."""
        if self.counts.comic:
            self.librarian_queue.put(ReadingListRematchTask())

    def _sync_live(self) -> None:
        """Sync the lists whose collection items' comics this import changed."""
        if not any(getattr(self.counts, name) for name in _LIVE_COUNTERS):
            return
        status = ReadingListLiveStatus()
        self.status_controller.start(status)
        try:
            changed = sync_live()
            status.complete = changed
            if changed:
                self.log.info(f"Synced the collections of {changed} reading lists.")
                self.librarian_queue.put(READING_LISTS_CHANGED_TASK)
        finally:
            self.status_controller.finish(status)

    def sync_reading_lists(self) -> None:
        """Bring the lists in step with this import: tags, then collections."""
        self._queue_rematch()
        self._sync_tag_lists()
        self._sync_live()

    def _sync_tag_lists(self) -> None:
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

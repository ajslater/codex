"""Sync the reading lists that come from story-arc tags after an import."""

from codex.librarian.scribe.importer.moved import MovedImporter
from codex.librarian.scribe.readinglists.status import ReadingListSyncStatus
from codex.librarian.scribe.readinglists.sync import sync_tag_lists

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

    def sync_reading_lists(self) -> None:
        """Bring the lists from story-arc tags in step with this import."""
        if not self._arc_links_may_have_changed():
            return
        status = ReadingListSyncStatus()
        self.status_controller.start(status)
        try:
            counts = sync_tag_lists()
            if counts.changed:
                self.log.info(f"Reading lists from tags: {counts}.")
        finally:
            self.status_controller.finish(status)

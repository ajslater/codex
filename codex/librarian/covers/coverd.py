"""Functions for dealing with comic cover thumbnails."""

from typing import override

from codex.librarian.covers.purge import CoverPurgeThread
from codex.librarian.covers.tasks import (
    CoverCreateAllTask,
    CoverCreateTask,
    CoverRemoveAllTask,
    CoverRemoveOrphansTask,
    CoverRemoveTask,
)


class CoverThread(CoverPurgeThread):
    """Create comic covers in it's own thread."""

    @override
    def process_item(self, item) -> None:
        """Run the task method."""
        match item:
            case CoverRemoveAllTask():
                self.purge_all_comic_covers(self.librarian_queue)
            case CoverRemoveTask():
                self.purge_comic_covers(item.pks, custom=item.custom)
            case CoverRemoveOrphansTask():
                self.cleanup_orphan_covers()
            case CoverCreateAllTask():
                self.create_all_covers()
            case CoverCreateTask():
                self.process_cover_create_burst(item)
            case _:
                self.log.error(f"Bad task sent to {self.__class__.__name__}: {item}")

"""Functions for dealing with comic cover thumbnails."""

from codex.librarian.covers.purge import CoverPurgeThread
from codex.librarian.covers.tasks import (
    CoverCreateAllTask,
    CoverRemoveAllTask,
    CoverRemoveOrphansTask,
    CoverRemoveTask,
    CoverSaveToCache,
)


class CoverThread(CoverPurgeThread):
    """Create comic covers in it's own thread."""

    def process_item(self, item):
        """Run the task method."""
        task = item
        if isinstance(task, CoverSaveToCache):
            self.save_cover_to_cache(task.cover_path, task.data)
        elif isinstance(task, CoverRemoveAllTask):
            self.purge_all_comic_covers(self.librarian_queue)
        elif isinstance(task, CoverRemoveTask):
            self.purge_comic_covers(task.pks, task.custom)
        elif isinstance(task, CoverRemoveOrphansTask):
            self.cleanup_orphan_covers()
        elif isinstance(task, CoverCreateAllTask):
            self.create_all_covers()
        else:
            self.log.error(f"Bad task sent to {self.__class__.__name__}: {task}")

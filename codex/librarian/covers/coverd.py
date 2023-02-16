"""Functions for dealing with comic cover thumbnails."""
from codex.librarian.covers.create import CoverCreateMixin
from codex.librarian.covers.purge import CoverPurgeMixin
from codex.librarian.covers.tasks import (
    CoverBulkCreateTask,
    CoverCreateTask,
    CoverRemoveAllTask,
    CoverRemoveOrphansTask,
    CoverRemoveTask,
    CoverSaveToCache,
)


class CoverCreatorThread(CoverCreateMixin, CoverPurgeMixin):
    """Create comic covers in it's own thread."""

    def process_item(self, task):
        """Run the creator."""
        if isinstance(task, CoverSaveToCache):
            self.save_cover_to_cache(task.cover_path, task.data)
        elif isinstance(task, CoverRemoveAllTask):
            self.purge_all_comic_covers(self.librarian_queue)
        elif isinstance(task, CoverRemoveTask):
            self.purge_comic_covers(task.comic_pks)
        elif isinstance(task, CoverRemoveOrphansTask):
            self.cleanup_orphan_covers()

        #####################
        # UNUSED BELOW HERE #
        #####################

        elif isinstance(task, CoverCreateTask):
            self.create_cover(task.pk)
        elif isinstance(task, CoverBulkCreateTask):
            self.bulk_create_comic_covers(task.comic_pks)
        else:
            self.log.error(f"Bad task sent to {self.__class__.__name__}: {task}")

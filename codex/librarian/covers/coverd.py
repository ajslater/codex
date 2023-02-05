"""Functions for dealing with comic cover thumbnails."""
from codex.librarian.covers.create import CoverCreateMixin
from codex.librarian.covers.purge import CoverPurgeMixin
from codex.librarian.covers.tasks import (
    CoverBulkCreateTask,
    CoverCreateTask,
    CoverRemoveAllTask,
    CoverRemoveOrphansTask,
    CoverRemoveTask,
    NewCoverCreateTask,
)


class CoverCreator(CoverCreateMixin, CoverPurgeMixin):
    """Create comic covers in it's own thread."""

    NAME = "CoverCreator"  # type: ignore

    def process_item(self, task):
        """Run the creator."""
        if isinstance(task, NewCoverCreateTask):
            self.new_create_cover(task.pk)
        if isinstance(task, CoverCreateTask):
            self.create_comic_cover(task.path, task.data)
        elif isinstance(task, CoverBulkCreateTask):
            self.bulk_create_comic_covers(task.comic_pks)
        elif isinstance(task, CoverRemoveAllTask):
            self.purge_all_comic_covers(self.librarian_queue)
        elif isinstance(task, CoverRemoveTask):
            self.purge_comic_covers(task.comic_pks)
        elif isinstance(task, CoverRemoveOrphansTask):
            self.cleanup_orphan_covers()
        else:
            self.logger.error(f"Bad task sent to {self.NAME}: {task}")

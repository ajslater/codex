"""Functions for dealing with comic cover thumbnails."""
from codex.librarian.covers.create import (
    bulk_create_comic_covers,
    create_comic_cover,
    create_comic_covers_for_libraries,
)
from codex.librarian.covers.purge import (
    cleanup_orphan_covers,
    purge_all_comic_covers,
    purge_comic_covers,
    purge_library_covers,
)
from codex.librarian.covers.tasks import (
    CoverBulkCreateTask,
    CoverCreateForLibrariesTask,
    CoverCreateTask,
    CoverRemoveAllTask,
    CoverRemoveForLibrariesTask,
    CoverRemoveOrphansTask,
    CoverRemoveTask,
)
from codex.settings.logging import get_logger
from codex.threads import QueuedThread


LOG = get_logger(__name__)


class CoverCreator(QueuedThread):
    """Create comic covers in it's own thread."""

    NAME = "CoverCreator"

    def process_item(self, task):
        """Run the creator."""
        if isinstance(task, CoverCreateTask):
            create_comic_cover(task.path, task.data)
        elif isinstance(task, CoverBulkCreateTask):
            bulk_create_comic_covers(task.comic_pks)
        elif isinstance(task, CoverCreateForLibrariesTask):
            create_comic_covers_for_libraries(task.library_ids)
        elif isinstance(task, CoverRemoveAllTask):
            purge_all_comic_covers()
        elif isinstance(task, CoverRemoveForLibrariesTask):
            purge_library_covers(task.library_ids)
        elif isinstance(task, CoverRemoveTask):
            purge_comic_covers(task.comic_pks)
        elif isinstance(task, CoverRemoveOrphansTask):
            cleanup_orphan_covers()
        else:
            LOG.error(f"Bad task sent to {self.NAME}: {task}")

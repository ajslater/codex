"""Functions for dealing with comic cover thumbnails."""
from logging import getLogger

from codex.librarian.covers.create import (
    bulk_create_comic_covers,
    create_comic_cover,
    create_comic_cover_for_libraries,
)
from codex.librarian.covers.purge import purge_cover_paths, purge_library_covers
from codex.librarian.queue_mp import (
    BulkComicCoverCreateTask,
    CreateComicCoversLibrariesTask,
    ImageComicCoverCreateTask,
    PurgeComicCoversLibrariesTask,
    PurgeComicCoversTask,
)
from codex.threads import QueuedThread


LOG = getLogger(__name__)


class CoverCreator(QueuedThread):
    """Create comic covers in it's own thread."""

    NAME = "CoverCreator"

    def _process_item(self, task):
        """Run the creator."""
        if isinstance(task, BulkComicCoverCreateTask):
            bulk_create_comic_covers(task.comics, task.force)
        elif isinstance(task, ImageComicCoverCreateTask):
            create_comic_cover(task.comic_path, task.image_data, task.cover_path)
        elif isinstance(task, CreateComicCoversLibrariesTask):
            create_comic_cover_for_libraries(task.library_ids)
        elif isinstance(task, PurgeComicCoversLibrariesTask):
            purge_library_covers(task.library_ids)
        elif isinstance(task, PurgeComicCoversTask):
            purge_cover_paths(task.cover_paths)
        else:
            LOG.error(f"Bad task sent to {self.NAME}: {task}")

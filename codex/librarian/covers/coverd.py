"""Functions for dealing with comic cover thumbnails."""
from codex.librarian.covers.cleanup import cleanup_orphan_covers
from codex.librarian.covers.create import (
    bulk_create_comic_covers,
    create_comic_cover,
    create_comic_cover_for_libraries,
    create_missing_covers,
)
from codex.librarian.covers.purge import purge_cover_paths, purge_library_covers
from codex.librarian.queue_mp import (
    BulkComicCoverCreateTask,
    CleanupMissingComicCovers,
    CreateComicCoversLibrariesTask,
    CreateMissingCoversTask,
    ImageComicCoverCreateTask,
    PurgeComicCoversLibrariesTask,
    PurgeComicCoversTask,
)
from codex.settings.logging import get_logger
from codex.threads import QueuedThread


LOG = get_logger(__name__)


class CoverCreator(QueuedThread):
    """Create comic covers in it's own thread."""

    NAME = "CoverCreator"

    def process_item(self, task):
        """Run the creator."""
        if isinstance(task, BulkComicCoverCreateTask):
            bulk_create_comic_covers(task.comics, task.force)
        elif isinstance(task, ImageComicCoverCreateTask):
            create_comic_cover(task.comic_path, task.cover_image_data)
        elif isinstance(task, CreateComicCoversLibrariesTask):
            create_comic_cover_for_libraries(task.library_ids)
        elif isinstance(task, PurgeComicCoversLibrariesTask):
            purge_library_covers(task.library_ids)
        elif isinstance(task, PurgeComicCoversTask):
            purge_cover_paths(task.cover_paths)
        elif isinstance(task, CreateMissingCoversTask):
            create_missing_covers()
        elif isinstance(task, CleanupMissingComicCovers):
            cleanup_orphan_covers()
        else:
            LOG.error(f"Bad task sent to {self.NAME}: {task}")

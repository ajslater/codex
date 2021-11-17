"""Clean up the database after moves or imports."""
from logging import getLogger

from codex.models import (
    Character,
    Comic,
    Credit,
    CreditPerson,
    CreditRole,
    Folder,
    Genre,
    Imprint,
    Location,
    Publisher,
    Series,
    SeriesGroup,
    StoryArc,
    Tag,
    Team,
    Volume,
)
from codex.librarian.queue_mp import LIBRARIAN_QUEUE, PurgeComicCoversTask


DELETE_COMIC_FKS = (
    Volume,
    Series,
    Imprint,
    Publisher,
    Folder,
    Credit,
    Tag,
    Team,
    Character,
    Location,
    SeriesGroup,
    StoryArc,
    Genre,
)
DELETE_CREDIT_FKS = (CreditRole, CreditPerson)
LOG = getLogger(__name__)


def bulk_folders_deleted(library, delete_folder_paths=None) -> bool:
    """Bulk delete folders."""
    if not delete_folder_paths:
        return False
    query = Folder.objects.filter(library=library, path__in=delete_folder_paths)
    query.delete()
    num_delete_folder_paths = len(delete_folder_paths)
    LOG.info(f"Deleted {num_delete_folder_paths} comics from {library.path}")
    return num_delete_folder_paths > 0


def bulk_comics_deleted(library, delete_comic_paths=None) -> bool:
    """Bulk delete comics found missing from the filesystem."""
    if not delete_comic_paths:
        return False
    query = Comic.objects.filter(library=library, path__in=delete_comic_paths)
    delete_cover_paths = query.values_list("cover_path", flat=True)

    LIBRARY_QUEUE.put(PurgeComicCoversTask(delete_cover_paths))

    query.delete()
    num_delete_cover_paths = len(delete_cover_paths)
    LOG.info(f"Deleted {num_delete_cover_paths} comics from {library.path}")
    return num_delete_cover_paths > 0

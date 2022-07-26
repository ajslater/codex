"""Clean up the database after moves or imports."""
from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.db.status import ImportStatusKeys
from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.librarian.status import librarian_status_done
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
from codex.settings.logging import get_logger


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
LOG = get_logger(__name__)


def bulk_folders_deleted(library, delete_folder_paths=None) -> bool:
    """Bulk delete folders."""
    if not delete_folder_paths:
        librarian_status_done([ImportStatusKeys.DIRS_DELETED])
        return False
    query = Folder.objects.filter(library=library, path__in=delete_folder_paths)
    count = query.count()
    query.delete()
    librarian_status_done([ImportStatusKeys.DIRS_DELETED])
    log = f"Deleted {count} folders from {library.path}"
    if count:
        LOG.info(log)
    else:
        LOG.verbose(log)
    return count > 0


def bulk_comics_deleted(library, delete_comic_paths=None) -> bool:
    """Bulk delete comics found missing from the filesystem."""
    if not delete_comic_paths:
        librarian_status_done([ImportStatusKeys.FILES_DELETED])
        return False
    query = Comic.objects.filter(library=library, path__in=delete_comic_paths)
    delete_comic_pks = frozenset(query.values_list("pk", flat=True))
    task = CoverRemoveTask(delete_comic_pks)
    LIBRARIAN_QUEUE.put(task)

    count = len(delete_comic_pks)
    query.delete()
    librarian_status_done([ImportStatusKeys.FILES_DELETED])
    log = f"Deleted {count} comics from {library.path}"
    if count:
        LOG.info(log)
    else:
        LOG.verbose(log)
    return count > 0

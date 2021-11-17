"""Bulk import and move comics and folders."""
from logging import getLogger

from codex.librarian.bulk_import.aggregate_metadata import get_aggregate_metadata
from codex.librarian.bulk_import.cleanup import cleanup_database
from codex.librarian.bulk_import.create_comics import bulk_import_comics
from codex.librarian.bulk_import.create_fks import bulk_create_all_fks
from codex.librarian.bulk_import.deleted import (
    bulk_comics_deleted,
    bulk_folders_deleted,
)
from codex.librarian.bulk_import.moved import bulk_comics_moved, bulk_folders_moved
from codex.librarian.bulk_import.query_fks import query_all_missing_fks
from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    AdminNotifierTask,
    BroadcastNotifierTask,
    BulkActionTask,
)
from codex.models import FailedImport, Folder, Library
from codex.threads import QueuedThread


LOG = getLogger(__name__)
# Batching entire imports doesn't really seem neccissary. This code is left here
#   as a cautionary measure just in case.
# Move folder and move comics are not yet batched
BATCH_SIZE = 100000


def _bulk_create_comic_relations(library, fks) -> bool:
    """Query all foreign keys to determine what needs creating, then create them."""
    if not fks:
        return False

    create_fks, create_groups, create_paths, create_credits = query_all_missing_fks(
        library.path, fks
    )

    changed = bulk_create_all_fks(
        library, create_fks, create_groups, create_paths, create_credits
    )
    return changed


def _batch_modified_and_created(library, modified_paths, created_paths) -> bool:
    """Perform one batch of imports."""
    mds, m2m_mds, fks = get_aggregate_metadata(library, modified_paths | created_paths)

    changed = _bulk_create_comic_relations(library, fks)

    changed |= bulk_import_comics(library, created_paths, modified_paths, mds, m2m_mds)
    return changed


def _bulk_folders_modified(library, paths):
    """Update folders stat and nothing else."""
    if not paths:
        return False
    folders = Folder.objects.filter(library=library, path__in=paths).only("stat")
    update_folders = []
    for folder in folders:
        folder.set_stat()
        update_folders.append(folder)
    Folder.objects.bulk_update(update_folders, ["stat"])
    num_update_folders = len(update_folders)
    LOG.verbose(f"Modified {num_update_folders} folders")
    return num_update_folders > 0


def bulk_action(task):
    """Bulk import comics."""
    LOG.verbose(f"Updating Library {library.path}...")  # type: ignore
    library = Library.objects.get(pk=task.library_id)
    library.update_in_progress = True
    library.save()
    LIBRARIAN_QUEUE.put(AdminNotifierTask("SCAN_LIBRARY"))

    changed = False
    changed |= bulk_folders_moved(library, task.dirs_moved)
    changed |= bulk_comics_moved(library, task.files_moved)
    changed |= _bulk_folders_modified(library, task.dirs_modified)
    changed |= _batch_modified_and_created(
        library, task.files_modified, task.files_created
    )
    changed |= bulk_folders_deleted(library, task.dirs_deleted)
    changed |= bulk_comics_deleted(library, task.files_deleted)
    changed |= cleanup_database(library)

    library.update_in_progress = False
    library.save()
    if FailedImport.objects.all().exists():
        text = "FAILED_IMPORTS"
    else:
        text = "SCAN_DONE"
    LIBRARIAN_QUEUE.put(AdminNotifierTask(text))
    if changed:
        LIBRARIAN_QUEUE.put(BroadcastNotifierTask("LIBRARY_CHANGED"))


class Updater(QueuedThread):
    """A worker to handle all bulk database updates."""

    NAME = "Updater"

    def _process_item(self, task):
        """Run the updater."""
        if isinstance(task, BulkActionTask):
            bulk_action(task)
        else:
            LOG.error(f"Bad task sent to library updater {task}")

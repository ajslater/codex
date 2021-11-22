"""Bulk import and move comics and folders."""
import time

from logging import getLogger

from django.db.models.functions import Now

from codex.librarian.db.aggregate_metadata import get_aggregate_metadata
from codex.librarian.db.cleanup import cleanup_database
from codex.librarian.db.create_comics import bulk_import_comics
from codex.librarian.db.create_fks import bulk_create_all_fks, bulk_folders_modified
from codex.librarian.db.deleted import bulk_comics_deleted, bulk_folders_deleted
from codex.librarian.db.moved import bulk_comics_moved, bulk_folders_moved
from codex.librarian.db.query_fks import query_all_missing_fks
from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    AdminNotifierTask,
    BroadcastNotifierTask,
    DBDiffTask,
)
from codex.models import FailedImport, Library
from codex.threads import QueuedThread


LOG = getLogger(__name__)


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


def _batch_modified_and_created(
    library, modified_paths, created_paths
) -> tuple[bool, int]:
    """Perform one batch of imports."""
    mds, m2m_mds, fks, fis = get_aggregate_metadata(
        library, modified_paths | created_paths
    )

    changed = _bulk_create_comic_relations(library, fks)

    imported_count = bulk_import_comics(
        library, created_paths, modified_paths, mds, m2m_mds, fis
    )
    changed |= imported_count > 0
    return changed, imported_count


def _log_task(library, task):
    """Log what we're doing next."""
    LOG.info(f"Updating Library {library.path}...")  # type: ignore
    logs = []
    if task.dirs_moved:
        logs += [f"{len(task.dirs_moved)} folders to move"]
    if task.files_moved:
        logs += [f"{len(task.files_moved)} comics to move"]
    if task.dirs_modified:
        logs += [f"{len(task.dirs_modified)} folders to update"]
    if task.files_modified:
        logs += [f"{len(task.files_modified)} comics to update"]
    if task.files_created:
        logs += [f"{len(task.files_created)} comics to create"]
    if task.dirs_deleted:
        logs += [f"{len(task.dirs_deleted)} folders to delete"]
    if task.files_deleted:
        logs += [f"{len(task.files_deleted)} comics to delete"]

    for log in logs:
        LOG.verbose(f"  {log}.")  # type: ignore


def apply(task):
    """Bulk import comics."""
    start_time = time.time()
    library = Library.objects.get(pk=task.library_id)
    _log_task(library, task)
    library.update_in_progress = True
    library.save()
    LIBRARIAN_QUEUE.put(AdminNotifierTask("SCAN_LIBRARY"))

    changed = False
    changed |= bulk_folders_moved(library, task.dirs_moved)
    changed |= bulk_comics_moved(library, task.files_moved)
    changed |= bulk_folders_modified(library, task.dirs_modified)
    changed_comics, imported_count = _batch_modified_and_created(
        library, task.files_modified, task.files_created
    )
    changed |= changed_comics
    changed |= bulk_folders_deleted(library, task.dirs_deleted)
    changed |= bulk_comics_deleted(library, task.files_deleted)
    changed |= cleanup_database(library)

    Library.objects.filter(pk=task.library_id).update(
        update_in_progress=False, updated_at=Now()
    )
    if FailedImport.objects.all().exists():
        text = "FAILED_IMPORTS"
    else:
        text = "SCAN_DONE"
    LIBRARIAN_QUEUE.put(AdminNotifierTask(text))
    if changed:
        LIBRARIAN_QUEUE.put(BroadcastNotifierTask("LIBRARY_CHANGED"))
        elapsed_time = time.time() - start_time
        LOG.info(f"Updated libary {library.path} in {int(elapsed_time)} seconds.")
        suffix = ""
        if imported_count:
            cps = int(imported_count / elapsed_time)
            suffix = f" at {cps} comics per second."
        LOG.verbose(f"Imported {imported_count} comics{suffix}.")  # type: ignore


class Updater(QueuedThread):
    """A worker to handle all bulk database updates."""

    NAME = "Updater"

    def _process_item(self, task):
        """Run the updater."""
        if isinstance(task, DBDiffTask):
            apply(task)
        else:
            LOG.warning(f"Bad task sent to library updater {task}")

"""Bulk import and move comics and folders."""
import time

from pathlib import Path

from django.core.cache import cache
from django.db.models.functions import Now
from humanize import precisedelta

from codex.librarian.db.aggregate_metadata import get_aggregate_metadata
from codex.librarian.db.create_comics import bulk_import_comics
from codex.librarian.db.create_fks import bulk_create_all_fks, bulk_folders_modified
from codex.librarian.db.deleted import bulk_comics_deleted, bulk_folders_deleted
from codex.librarian.db.failed_imports import bulk_fail_imports
from codex.librarian.db.moved import bulk_comics_moved, bulk_folders_moved
from codex.librarian.db.query_fks import query_all_missing_fks
from codex.librarian.db.status import ImportStatusKeys
from codex.librarian.db.tasks import UpdaterDBDiffTask
from codex.librarian.queue_mp import LIBRARIAN_QUEUE, DelayedTasks
from codex.librarian.search.tasks import SearchIndexJanitorUpdateTask
from codex.librarian.status import librarian_status_update
from codex.models import Library
from codex.notifier.tasks import (
    FAILED_IMPORTS_TASK,
    LIBRARIAN_STATUS_TASK,
    LIBRARY_CHANGED_TASK,
)
from codex.settings.logging import LOG_EVERY, VERBOSE, get_logger
from codex.threads import QueuedThread


WRITE_WAIT_EXPIRY = LOG_EVERY
LOG = get_logger(__name__)


def _wait_for_filesystem_ops_to_finish(task: UpdaterDBDiffTask) -> bool:
    """Watchdog sends events before filesystem events finish, so wait for them."""
    started_checking = time.time()

    # Don't wait for deletes to complete.
    # Do wait for move, modified, create files before import.
    all_modified_paths = (
        frozenset(task.dirs_moved.values())
        | frozenset(task.files_moved.values())
        | task.dirs_modified
        | task.files_modified
        | task.files_created
    )

    old_total_size = -1
    total_size = 0
    wait_time = 2
    while old_total_size != total_size:
        if old_total_size > 0:
            # second time around or more
            time.sleep(wait_time)
            wait_time = wait_time**2
            LOG.verbose(
                f"Waiting for files to copy before import: "
                f"{old_total_size} != {total_size}"
            )
        if time.time() - started_checking > WRITE_WAIT_EXPIRY:
            return True

        old_total_size = total_size
        total_size = 0
        for path_str in all_modified_paths:
            path = Path(path_str)
            if path.exists():
                total_size += Path(path).stat().st_size
    return False


def _bulk_create_comic_relations(library, fks) -> bool:
    """Query all foreign keys to determine what needs creating, then create them."""
    if not fks:
        return False

    (
        create_fks,
        create_groups,
        update_groups,
        create_paths,
        create_credits,
    ) = query_all_missing_fks(library.path, fks)

    changed = bulk_create_all_fks(
        library, create_fks, create_groups, update_groups, create_paths, create_credits
    )
    return changed


def _batch_modified_and_created(
    library, modified_paths, created_paths
) -> tuple[bool, int, bool]:
    """Perform one batch of imports."""
    mds, m2m_mds, fks, fis = get_aggregate_metadata(
        library, modified_paths | created_paths
    )
    modified_paths -= fis.keys()
    created_paths -= fis.keys()

    changed = _bulk_create_comic_relations(library, fks)

    imported_count = bulk_import_comics(
        library, created_paths, modified_paths, mds, m2m_mds
    )
    new_failed_imports = bulk_fail_imports(library, fis)
    changed |= imported_count > 0
    return changed, imported_count, new_failed_imports


def _log_task(path, task):
    if LOG.getEffectiveLevel() < VERBOSE:
        return
    LOG.verbose(f"Updating library {path}...")
    dirs_log = []
    if task.dirs_moved:
        dirs_log += [f"{len(task.dirs_moved)} moved"]
    if task.dirs_modified:
        dirs_log += [f"{len(task.dirs_modified)} modified"]
    if task.dirs_deleted:
        dirs_log += [f"{len(task.dirs_deleted)} deleted"]
    comics_log = []
    if task.files_moved:
        comics_log += [f"{len(task.files_moved)} moved"]
    if task.files_modified:
        comics_log += [f"{len(task.files_modified)} modified"]
    if task.files_created:
        comics_log += [f"{len(task.files_created)} created"]
    if task.files_deleted:
        comics_log += [f"{len(task.files_deleted)} deleted"]

    if comics_log:
        log = "Comics: "
        log += ", ".join(comics_log)
        LOG.verbose("  " + log)
    if dirs_log:
        log = "Folders: "
        log += ", ".join(dirs_log)
        LOG.verbose("  " + log)


def _init_librarian_status(task, path, total_paths):
    """Update the librarian status tasks."""
    # TODO could be a bulk import
    if task.files_moved:
        librarian_status_update(
            ImportStatusKeys.FILES_MOVED, 0, len(task.files_moved), notify=False
        )
    if total_paths:
        status_keys = {**ImportStatusKeys.AGGREGATE_STATUS_KEYS, "name": path}
        librarian_status_update(status_keys, 0, total_paths, notify=False)
        librarian_status_update(
            ImportStatusKeys.QUERY_MISSING_FKS, 0, None, notify=False
        )
        librarian_status_update(ImportStatusKeys.CREATE_FKS, 0, None, notify=False)
        librarian_status_update(ImportStatusKeys.LINK_M2M_FIELDS, 0, None, notify=False)
        if task.files_modified:
            librarian_status_update(
                ImportStatusKeys.FILES_MODIFIED,
                0,
                len(task.files_modified),
                notify=False,
            )
        if task.files_created:
            librarian_status_update(
                ImportStatusKeys.FILES_CREATED, 0, len(task.files_created), notify=False
            )
    if task.files_deleted:
        librarian_status_update(
            ImportStatusKeys.FILES_DELETED, 0, len(task.files_deleted), notify=False
        )
    LIBRARIAN_QUEUE.put(LIBRARIAN_STATUS_TASK)


def _apply(task):
    """Bulk import comics."""
    start_time = time.time()
    library = Library.objects.get(pk=task.library_id)
    _log_task(library.path, task)
    library.update_in_progress = True
    library.save()
    _init_librarian_status(
        task, library.path, len(task.files_modified) + len(task.files_created)
    )
    too_long = _wait_for_filesystem_ops_to_finish(task)
    if too_long:
        LOG.warning(
            "Import apply waited for the filesystem to stop changing too long. "
            "Try polling again once files have finished copying."
        )
        return

    changed = False
    changed |= bulk_folders_moved(library, task.dirs_moved)
    changed |= bulk_comics_moved(library, task.files_moved)
    changed |= bulk_folders_modified(library, task.dirs_modified)
    changed_comics, imported_count, new_failed_imports = _batch_modified_and_created(
        library, task.files_modified, task.files_created
    )
    changed |= changed_comics
    changed |= bulk_folders_deleted(library, task.dirs_deleted)
    changed |= bulk_comics_deleted(library, task.files_deleted)
    cache.clear()

    Library.objects.filter(pk=task.library_id).update(
        update_in_progress=False, updated_at=Now()
    )
    # Wait to start the search index update in case more updates are incoming.
    delayed_search_task = DelayedTasks(2, (SearchIndexJanitorUpdateTask(False),))
    LIBRARIAN_QUEUE.put(delayed_search_task)

    if changed:
        LIBRARIAN_QUEUE.put(LIBRARY_CHANGED_TASK)
        elapsed_time = time.time() - start_time
        LOG.info(
            f"Updated library {library.path} in {precisedelta(int(elapsed_time))}."
        )
        suffix = ""
        if imported_count:
            cps = int(imported_count / elapsed_time)
            suffix = f" at {cps} comics per second."
        LOG.verbose(f"Imported {imported_count} comics{suffix}.")
    if new_failed_imports:
        LIBRARIAN_QUEUE.put(FAILED_IMPORTS_TASK)


class Updater(QueuedThread):
    """A worker to handle all bulk database updates."""

    NAME = "Updater"

    def process_item(self, task):
        """Run the updater."""
        if isinstance(task, UpdaterDBDiffTask):
            _apply(task)
        else:
            LOG.warning(f"Bad task sent to library updater {task}")

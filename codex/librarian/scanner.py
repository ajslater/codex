"""Scan librarys for comics."""
import os

from datetime import datetime
from logging import getLogger
from pathlib import Path

from django.utils import timezone

from codex.librarian.bulk_import.main import (
    bulk_comics_moved,
    bulk_folders_moved,
    bulk_import,
)
from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    AdminNotifierTask,
    BroadcastNotifierTask,
    BulkComicMovedTask,
    BulkFolderMovedTask,
    ScannerCronTask,
    ScanRootTask,
)
from codex.librarian.regex import COMIC_MATCHER
from codex.models import SCHEMA_VERSION, Comic, FailedImport, Library
from codex.threads import QueuedThread


LOG = getLogger(__name__)


def _is_outdated(path, updated_at):
    """Compare the db updated_at time to the filesystem time."""
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    mtime = timezone.make_aware(mtime, timezone.get_default_timezone())
    return mtime > updated_at


def _scan_existing(library, force):
    """Scan existing comics for updates."""
    LOG.verbose(f"Scanning for existing comics {force=}")  # type: ignore
    comics = Comic.objects.filter(library=library).values_list("path", "updated_at")

    delete_paths = set()
    update_comic_paths = set()
    all_comic_paths = set()
    for path, updated_at in comics:
        path = Path(path)
        all_comic_paths.add(path)
        if not path.is_file():
            delete_paths.add(path)
        elif force or _is_outdated(path, updated_at):
            update_comic_paths.add(path)
    LOG.verbose(  # type: ignore
        f"Scanned {len(update_comic_paths)} outdated comics, "
        f"{len(delete_paths)} missing comics."
    )
    return all_comic_paths, update_comic_paths, delete_paths


def _scan_new(library_path, all_comic_paths):
    """Add comics from a library that aren't in the db already."""
    LOG.verbose("Scanning for new comics...")  # type: ignore
    create_comic_paths = set()
    for root, _, filenames in os.walk(library_path):
        walk_root = Path(root)
        LOG.debug(f"Scanning {walk_root}")
        for filename in filenames:
            if COMIC_MATCHER.search(filename) is None:
                continue
            path = walk_root / filename
            if path not in all_comic_paths:
                create_comic_paths.add(path)
    LOG.verbose(f"Scanned {len(create_comic_paths)} new comics")  # type: ignore
    return create_comic_paths


def _scan_and_import(library, force):
    all_paths, update_paths, delete_paths = _scan_existing(library, force)
    create_paths = _scan_new(library.path, all_paths)
    total_imported, num_deleted = bulk_import(
        library=library,
        update_paths=update_paths,
        create_paths=create_paths,
        delete_paths=delete_paths,
    )
    return total_imported, num_deleted


class NoLibraryPathError(Exception):
    """Break out if no library found."""

    pass


def _scan_root(pk, force=False):
    """Scan a library."""
    library = Library.objects.only("scan_in_progress", "last_scan", "path").get(pk=pk)
    notifier_text = "SCAN_DONE"
    if library.scan_in_progress:
        LOG.info(f"Scan in progress for {library.path}. Not rescanning")
        return notifier_text
    count = num_deleted = 0
    try:
        if not Path(library.path).is_dir():
            raise NoLibraryPathError()
        LOG.info(f"Scanning {library.path}...")
        library.scan_in_progress = True
        library.save()
        force = force or library.last_scan is None
        start_time = datetime.now()
        count, num_deleted = _scan_and_import(library, force)
        elapsed_time = datetime.now() - start_time
        if count:
            log_suffix = f" {elapsed_time/count} s/comic."
        else:
            count = "no"
            log_suffix = "."
        LOG.info(
            f"Scan and import {library.path} {elapsed_time}s "
            f"for {count} comics{log_suffix}"
        )
        if force or library.last_scan is None or library.schema_version is None:
            library.schema_version = SCHEMA_VERSION
        library.last_scan = timezone.now()
        LOG.info(f"Scan of {library.path} finished.")
    except NoLibraryPathError:
        LOG.warning(f"Could not find library at {library.path}. Not scanning.")
    except Exception as exc:
        LOG.exception(exc)
    finally:
        library.scan_in_progress = False
        library.save()
    is_failed_imports = FailedImport.objects.exists()
    changed = bool(count or num_deleted)
    if is_failed_imports:
        notifier_text = "FAILED_IMPORTS"
    return notifier_text, changed


def _is_time_to_scan(library):
    """Determine if its time to scan this library."""
    if library.last_scan is None:
        return True

    since_last_scan = timezone.now() - library.last_scan
    if since_last_scan > library.scan_frequency:
        return True

    return False


def _scan_cron():
    """Regular cron for scanning."""
    librarys = Library.objects.filter(enable_scan_cron=True).only(
        "pk", "schema_version", "last_scan"
    )
    aggregate_text = "SCAN_DONE"
    aggregate_changed = False
    for library in librarys:
        try:
            force_import = library.schema_version < SCHEMA_VERSION
            if _is_time_to_scan(library) or force_import:
                text, changed = _scan_root(library.pk, force_import)
                if aggregate_text and aggregate_text != "FAILED_IMPORTS":
                    aggregate_text = text
                aggregate_changed = aggregate_changed or changed
        except Exception as exc:
            LOG.error(exc)
    return aggregate_text, aggregate_changed


class Scanner(QueuedThread):
    """A worker to handle all scanning, importing and moving."""

    NAME = "Scanner"

    def _process_item(self, task):
        """Run the scanner."""
        LIBRARIAN_QUEUE.put(AdminNotifierTask("SCAN_LIBRARY"))
        text = "SCAN_DONE"
        changed = True
        if isinstance(task, ScannerCronTask):
            text, changed = _scan_cron()
        elif isinstance(task, ScanRootTask):
            text, changed = _scan_root(task.library_id, task.force)
        elif isinstance(task, BulkFolderMovedTask):
            bulk_folders_moved(task.library_id, task.moved_paths)
        elif isinstance(task, BulkComicMovedTask):
            bulk_comics_moved(task.library_id, task.moved_paths)
        else:
            LOG.error(f"Bad task sent to scanner {task}")
        LIBRARIAN_QUEUE.put(AdminNotifierTask(text))
        if changed:
            LIBRARIAN_QUEUE.put(BroadcastNotifierTask("LIBRARY_CHANGED"))

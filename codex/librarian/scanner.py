"""Scan librarys for comics."""
import logging
import os

from datetime import datetime
from pathlib import Path

from django.utils import timezone

from codex.librarian.bulk_import.main import bulk_import
from codex.librarian.queue_mp import QUEUE, ScanDoneTask, ScanRootTask
from codex.librarian.regex import COMIC_MATCHER
from codex.models import SCHEMA_VERSION, Comic, FailedImport, Library


LOG = logging.getLogger(__name__)


def _is_outdated(path, updated_at):
    """Compare the db updated_at time to the filesystem time."""
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    mtime = timezone.make_aware(mtime, timezone.get_default_timezone())
    return mtime > updated_at


def _bulk_scan_existing(library, force):
    """Scan existing comics for updates"""
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
    return all_comic_paths, update_comic_paths, delete_paths


def _bulk_scan_new(library_path, all_comic_paths):
    """Add comics from a library that aren't in the db already."""
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
    return create_comic_paths


def _bulk_scan_and_import(library, force):
    all_paths, update_paths, delete_paths = _bulk_scan_existing(library, force)
    create_paths = _bulk_scan_new(library.path, all_paths)
    total_imported = bulk_import(
        library=library,
        update_paths=update_paths,
        create_paths=create_paths,
        delete_paths=delete_paths,
    )
    return total_imported


def scan_root(pk, force=False):
    """Scan a library."""
    library = Library.objects.only("scan_in_progress", "last_scan", "path").get(pk=pk)
    if library.scan_in_progress:
        LOG.info(f"Scan in progress for {library.path}. Not rescanning")
        return
    LOG.info(f"Scanning {library.path}...")
    library.scan_in_progress = True
    library.save()
    try:
        if not Path(library.path).is_dir():
            LOG.warning(f"Could not find {library.path}. Not scanning.")
            raise ValueError("no library path")
        force = force or library.last_scan is None
        start_time = datetime.now()
        count = _bulk_scan_and_import(library, force)
        elapsed_time = datetime.now() - start_time
        if count:
            log_suffix = f" {elapsed_time/count} s/comic."
        else:
            log_suffix = "."
        LOG.info(f"Scan and import {elapsed_time}s for {count} comics{log_suffix}")
        if force or library.last_scan is None or library.schema_version is None:
            library.schema_version = SCHEMA_VERSION
        library.last_scan = timezone.now()
    except Exception as exc:
        LOG.exception(exc)
    finally:
        library.scan_in_progress = False
        library.save()
    is_failed_imports = FailedImport.objects.exists()
    QUEUE.put(ScanDoneTask(failed_imports=is_failed_imports, sleep=0))
    LOG.info(f"Scan for {library.path} finished.")


def is_time_to_scan(library):
    """Determine if its time to scan this library."""
    if library.last_scan is None:
        return True

    since_last_scan = timezone.now() - library.last_scan
    if since_last_scan > library.scan_frequency:
        return True

    return False


def scan_cron():
    """Regular cron for scanning."""
    librarys = Library.objects.filter(enable_scan_cron=True).only(
        "pk", "schema_version", "last_scan"
    )
    for library in librarys:
        force_import = library.schema_version < SCHEMA_VERSION
        if is_time_to_scan(library) or force_import:
            try:
                task = ScanRootTask(library.pk, force_import)
                QUEUE.put(task)
            except Exception as exc:
                LOG.error(exc)

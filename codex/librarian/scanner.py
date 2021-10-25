"""Scan librarys for comics."""
import logging
import os

from datetime import datetime
from pathlib import Path

from django.db.models import F
from django.utils import timezone

from codex.librarian.bulk_import.main import bulk_import
from codex.librarian.importer import COMIC_MATCHER
from codex.librarian.queue_mp import (
    QUEUE,
    ComicDeletedTask,
    ComicModifiedTask,
    FolderDeletedTask,
    ScanDoneTask,
    ScanRootTask,
)
from codex.models import SCHEMA_VERSION, Comic, FailedImport, Folder, Library


LOG = logging.getLogger(__name__)

# ================ OLD INDIVIDUAL SCANNING ============================================


def scan_for_new(library):
    """Add comics from a library that aren't in the db already."""
    # Will hafta check each comic's updated_at once I allow writing
    LOG.info(f"Scanning {library.path}")
    num_new = 0
    num_skipped = 0
    num_passed = 0
    for root, _, filenames in os.walk(library.path):
        walk_root = Path(root)
        LOG.debug(f"Scanning {walk_root}")
        for filename in sorted(filenames):
            path = walk_root / filename
            if COMIC_MATCHER.search(str(path)) is not None:
                if not Comic.objects.filter(path=path).exists():
                    task = ComicModifiedTask(path, library.id)
                    QUEUE.put(task)
                    num_new += 1
                else:
                    num_passed += 1
            else:
                num_skipped += 1

    LOG.info(f"Queued {num_new} comics for import.")
    LOG.debug(f"Skipped {num_skipped} non-comic files.")
    LOG.debug(f"Ignored {num_passed} comics already in the db.")
    return num_new


def is_obj_outdated(obj):
    """Compare the db updated_at time to the filesystem time."""
    path = Path(obj.path)
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    mtime = timezone.make_aware(mtime, timezone.get_default_timezone())
    return mtime > obj.updated_at


def scan_existing(library, cls, force=False):
    """
    Scan existing comics and folders.

    Remove the missing ones. Update the outated comics.
    """
    num_removed = 0
    num_updated = 0
    num_passed = 0
    objs = cls.objects.filter(library=library).only("path")
    for obj in objs:
        path = Path(obj.path)
        task = None
        if cls == Folder and not path.is_dir():
            task = FolderDeletedTask(obj.path)
        elif cls == Comic and not path.is_file():
            task = ComicDeletedTask(obj.path)
        if task:
            num_removed += 1
        elif cls == Comic and (force or is_obj_outdated(obj)):
            task = ComicModifiedTask(obj.path, library.id)
            num_updated += 1

        if task:
            QUEUE.put(task)
        else:
            num_passed += 1

    cls_name = cls.__name__.lower()
    LOG.info(f"Queued {num_removed} {cls_name}s for removal.")
    if cls == Comic:
        LOG.info(f"Queued {num_updated} {cls_name}s for re-import.")
    LOG.debug(f"Ignored {num_passed} {cls_name}s that are up to date.")
    return num_updated


def cleanup_failed_imports(library):
    """Tidy up  the failed imports table."""
    # Cleanup FailedImports that were actually successful
    #  Should never trigger because of the per import cleanup in imports
    FailedImport.objects.filter(
        library=library, path=F("library__comic__path")
    ).delete()

    # Cleanup FailedImports that aren't on the filesystem anymore.
    failed_imports = FailedImport.objects.only("library", "path").filter(
        library=library
    )
    for failed_import in failed_imports:
        if not Path(failed_import.path).exists():
            failed_import.delete()


def _scan_root_individual(library, force):
    num_updated = scan_existing(library, Comic, force)
    scan_existing(library, Folder)
    num_new = scan_for_new(library)
    cleanup_failed_imports(library)
    return num_updated + num_new


# ========== NEW BULK SCANNING ========================================================


def _is_outdated(path, updated_at):
    """Compare the db updated_at time to the filesystem time."""
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    mtime = timezone.make_aware(mtime, timezone.get_default_timezone())
    return mtime > updated_at


def _bulk_scan_existing(library_pk, force):
    """Scan existing comics for updates"""
    comics = Comic.objects.filter(library=library_pk).values_list(
        "pk", "path", "cover_path", "updated_at"
    )

    delete_comics = {}
    update_comic_paths = set()
    for pk, path, cover_path, updated_at in comics:
        path = Path(path)
        if not path.is_file():
            delete_comics[pk] = cover_path
        elif force or _is_outdated(path, updated_at):
            update_comic_paths.add(path)
    return update_comic_paths, dict(delete_comics)


def _bulk_scan_new(library):
    """Add comics from a library that aren't in the db already."""
    comic_paths = Comic.objects.filter(library=library).values_list("path", flat=True)
    comic_paths = set(comic_paths)
    create_comic_paths = set()
    for root, _, filenames in os.walk(library.path):
        walk_root = Path(root)
        LOG.debug(f"Scanning {walk_root}")
        for filename in filenames:
            if COMIC_MATCHER.search(filename) is None:
                continue
            path = walk_root / filename
            if str(path) not in comic_paths:
                create_comic_paths.add(path)
    return create_comic_paths


def _bulk_scan_and_import(library, force):
    update_paths, delete_comics = _bulk_scan_existing(library.pk, force)
    create_paths = _bulk_scan_new(library)
    bulk_import(library, update_paths, create_paths, delete_comics)
    return len(update_paths) + len(create_paths)


def scan_root(pk, force=False, bulk=False):
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
        if bulk:
            count = _bulk_scan_and_import(library, force)
        else:
            count = _scan_root_individual(library, force)
        elapsed_time = datetime.now() - start_time
        if count:
            log_suffix = f" {elapsed_time/count} s/comic."
        else:
            log_suffix = "."
        LOG.info(
            f"Scan and import {bulk=} {elapsed_time}s for {count} comics{log_suffix}"
        )
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
                task = ScanRootTask(library.pk, force_import, False)
                QUEUE.put(task)
            except Exception as exc:
                LOG.error(exc)

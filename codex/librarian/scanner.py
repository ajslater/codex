"""Scan librarys for comics."""
import logging
import os

from datetime import datetime
from pathlib import Path

from django.utils import timezone

from codex.librarian.importer import COMIC_MATCHER
from codex.librarian.queue import QUEUE
from codex.librarian.queue import ComicDeletedTask
from codex.librarian.queue import ComicModifiedTask
from codex.librarian.queue import FolderDeletedTask
from codex.librarian.queue import ScanRootTask
from codex.models import SCHEMA_VERSION
from codex.models import Comic
from codex.models import Folder
from codex.models import Library


LOG = logging.getLogger(__name__)


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
        if Path(library.path).is_dir():
            force = force or library.last_scan is None
            scan_existing(library, Comic, force)
            scan_existing(library, Folder)
            scan_for_new(library)
            if force or library.last_scan is None or library.schema_version is None:
                library.schema_version = SCHEMA_VERSION
            library.last_scan = timezone.now()
        else:
            LOG.warning(f"Could not find {library.path}. Not scanning.")
    except Exception as exc:
        LOG.exception(exc)
    finally:
        library.scan_in_progress = False
        library.save()
    LOG.info(f"Scan for {library.path} finished.")


def scan_all_roots(force):
    """Scan all the librarys."""
    LOG.info("Scanning all librarys...")
    rps = Library.objects.all().only("pk")
    for library in rps:
        task = ScanRootTask(library.pk, force)
        QUEUE.put(task)


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

"""Scan root paths for comics."""
import logging
import os

from datetime import datetime
from pathlib import Path

from django.utils import timezone

from codex.library.importer import COMIC_MATCHER
from codex.library.queue import QUEUE
from codex.library.queue import ComicDeletedTask
from codex.library.queue import ComicModifiedTask
from codex.library.queue import FolderDeletedTask
from codex.library.queue import ScanRootTask
from codex.models import Comic
from codex.models import Folder
from codex.models import RootPath


LOG = logging.getLogger(__name__)


def scan_add(root_path, force=False):
    """Add or update comics from a root path."""
    # We could check each comic's updated_at, but that seems slow.
    LOG.info(f"Scanning {root_path.path} force: {force}")
    num_updated = 0
    num_skipped = 0
    num_passed = 0
    for root, dirnames, filenames in os.walk(root_path.path):
        walk_root = Path(root)
        LOG.debug(f"Scanning {walk_root}")
        for filename in sorted(filenames):
            path = walk_root / filename
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            mtime = timezone.make_aware(mtime, timezone.get_default_timezone())
            if COMIC_MATCHER.search(str(path)) is not None:
                if root_path.last_scan is None or mtime > root_path.last_scan or force:
                    task = ComicModifiedTask(path, root_path.id)
                    QUEUE.put(task)
                    num_updated += 1
                else:
                    num_passed += 1
            else:
                num_skipped += 1

    LOG.info(f"Queued {num_updated} comics for import.")
    LOG.info(f"Skipped {num_passed} unmodified files.")
    LOG.info(f"Skipped {num_skipped} non-comic files.")


def scan_missing(root_path, cls):
    """Find missing comics and folders."""
    num_removed = 0
    objs = cls.objects.filter(root_path=root_path)
    for obj in objs:
        path = Path(obj.path)
        if cls == Folder:
            exists = path.is_dir()
        else:
            exists = path.is_file()
        if not exists:
            if cls == Folder:
                task = FolderDeletedTask(obj.path)
            else:
                task = ComicDeletedTask(obj.path)
            QUEUE.put(task)
            num_removed += 1
            LOG.debug(f"Queued missing: {obj.display_name}")

    LOG.info(f"Queued {num_removed} to mark as missing.")


def scan_root(pk, force=False):
    """Scan a root path."""
    root_path = RootPath.objects.get(pk=pk)
    if root_path.scan_in_progress:
        LOG.info(f"Scan in progress for {root_path.path}. Not rescanning")
        return
    LOG.info(f"Scanning {root_path.path}...")
    root_path.scan_in_progress = True
    root_path.save()
    if Path(root_path.path).is_dir():
        scan_add(root_path, force)
        scan_missing(root_path, Comic)
        scan_missing(root_path, Folder)
        root_path.last_scan = timezone.now()
    else:
        LOG.warning(f"Could not find {root_path.path}. Not scanning.")
    root_path.scan_in_progress = False
    root_path.save()
    LOG.info(f"Scan for {root_path.path} finished.")


def scan_all_roots(force):
    """Scan all the root paths."""
    LOG.info("Scanning all root paths...")
    rps = RootPath.objects.all()
    for root_path in rps:
        task = ScanRootTask(root_path.pk, force)
        QUEUE.put(task)

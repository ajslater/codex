"""Purge comic covers."""
import os
import shutil

from pathlib import Path

from codex.librarian.covers.path import COVER_ROOT, get_cover_paths
from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.librarian.status import librarian_status_done, librarian_status_update
from codex.models import Comic, Timestamp
from codex.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.settings.logging import get_logger


COVER_PURGE_STATUS_KEYS = {"type": "Remove Covers"}
COVER_ORPHAN_FIND_STATUS_KEYS = {"type": "Finding Orphan Covers"}
LOG = get_logger(__name__)


def _cleanup_cover_dirs(path):
    """Recursively remove empty cover directories."""
    if not path or COVER_ROOT not in path.parents:
        return
    try:
        path.rmdir()
        _cleanup_cover_dirs(path.parent)
    except OSError:
        pass


def purge_cover_paths(cover_paths):
    """Purge a set a cover paths."""
    LOG.verbose(f"Removing {len(cover_paths)} cover thumbnails...")
    librarian_status_update(COVER_PURGE_STATUS_KEYS, 0, None)
    cover_dirs = set()
    for cover_path in cover_paths:
        cover_path.unlink(missing_ok=True)
        cover_dirs.add(cover_path.parent)
    for cover_dir in cover_dirs:
        _cleanup_cover_dirs(cover_dir)
    librarian_status_done([COVER_PURGE_STATUS_KEYS])
    LOG.info(f"Removed {len(cover_paths)} cover thumbnails.")


def purge_comic_covers(comic_pks):
    """Purge a set a cover paths."""
    cover_paths = get_cover_paths(comic_pks)
    purge_cover_paths(cover_paths)


def purge_library_covers(library_pks):
    """Remove all cover thumbs for a library."""
    LOG.verbose(f"Removing comic covers from libraries: {library_pks}")
    comic_pks = Comic.objects.filter(library_id__in=library_pks).values_list(
        "pk", flat=True
    )
    purge_comic_covers(comic_pks)


def purge_all_comic_covers():
    """Purge every comic cover."""
    LOG.verbose("Removing entire comic cover cache.")
    shutil.rmtree(COVER_ROOT)
    Timestamp.touch(Timestamp.COVERS)
    LOG.info("Removed entire comic cover cache.")
    LIBRARIAN_QUEUE.put(LIBRARY_CHANGED_TASK)


def cleanup_orphan_covers():
    """Remove all orphan cover thumbs."""
    LOG.verbose("Removing covers from missing comics.")
    librarian_status_update(COVER_ORPHAN_FIND_STATUS_KEYS, 0, None)
    comic_pks = Comic.objects.all().values_list("pk", flat=True)
    db_cover_paths = get_cover_paths(comic_pks)

    orphan_cover_paths = set()
    for root, _, filenames in os.walk(COVER_ROOT):
        root_path = Path(root)
        for fn in filenames:
            fs_cover_path = root_path / fn
            if fs_cover_path not in db_cover_paths:
                orphan_cover_paths.add(fs_cover_path)

    librarian_status_done([COVER_ORPHAN_FIND_STATUS_KEYS])
    purge_cover_paths(orphan_cover_paths)
    LOG.info(f"Removed {len(orphan_cover_paths)} covers for missing comics.")

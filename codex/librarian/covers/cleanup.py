"""Purge comic covers."""
import os

from codex.librarian.covers import COVER_ROOT
from codex.librarian.covers.purge import purge_cover_paths
from codex.models import Comic
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


def cleanup_orphan_covers():
    """Remove all orphan cover thumbs."""
    LOG.verbose("Removing covers from missing comics.")
    db_cover_paths = Comic.objects.filter().values_list("cover_path", flat=True)
    orphan_cover_paths = set()
    for _, _, filenames in os.walk(COVER_ROOT):
        for fn in filenames:
            if fn not in db_cover_paths:
                orphan_cover_paths.add(fn)

    purge_cover_paths(orphan_cover_paths)
    LOG.info(f"Removed {len(orphan_cover_paths)} covers for missing comics.")

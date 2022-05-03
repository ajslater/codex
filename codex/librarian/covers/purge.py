"""Purge comic covers."""
from pathlib import Path

from codex.librarian.covers import COVER_ROOT
from codex.models import Comic
from codex.settings.logging import get_logger


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


def _purge_cover_path(comic_cover_path):
    """Remove one cover thumb from the filesystem."""
    if not comic_cover_path:
        return
    cover_path = COVER_ROOT / comic_cover_path
    cover_path.unlink(missing_ok=True)


def purge_cover_paths(cover_paths):
    """Purge a set a cover paths."""
    cover_dirs = set()
    for cover_path in cover_paths:
        _purge_cover_path(cover_path)
        cover_dirs.add(Path(cover_path).parent)
    for cover_dir in cover_dirs:
        _cleanup_cover_dirs(cover_dir)


def purge_library_covers(library_pks):
    """Remove all cover thumbs for a library."""
    LOG.verbose(f"Removing comic covers from libraries: {library_pks}")
    cover_paths = Comic.objects.filter(library_id__in=library_pks).values_list(
        "cover_path", flat=True
    )
    purge_cover_paths(cover_paths)

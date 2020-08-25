import logging

from io import BytesIO
from pathlib import Path

from comicbox.comic_archive import ComicArchive
from PIL import Image

from codex.librarian.queue import QUEUE
from codex.librarian.queue import LibraryChangedTask
from codex.models import Comic
from codex.settings import CONFIG_STATIC


THUMBNAIL_SIZE = (120, 180)


COVER_ROOT = Path(f"{CONFIG_STATIC}/covers")
LOG = logging.getLogger(__name__)


def cleanup_cover_dirs(path):
    """Recursively remove empty cover directories"""
    if COVER_ROOT not in path.parents:
        return
    try:
        path.rmdir()
        cleanup_cover_dirs(path.parent)
    except OSError:
        pass


def purge_cover(comic):
    """Remove one cover thumb from the filesystem."""
    cover_path = COVER_ROOT / comic.cover_path
    try:
        # XXX python 3.8 missing_ok=True
        # Switch to python 3.8 requirement begginning of 2021
        cover_path.unlink()
    except FileNotFoundError:
        pass
    cleanup_cover_dirs(cover_path.parent)


def purge_all_covers(library):
    """Remove all cover thumbs for a library."""
    comics = Comic.objects.only("path", "library").filter(library=library)
    for comic in comics:
        purge_cover(comic)


def create_comic_cover(comic_path, db_cover_path, force=False):
    """Create a comic cover thumnail and save it to disk."""
    try:
        fs_cover_path = COVER_ROOT / db_cover_path
        if fs_cover_path.exists() and not force:
            LOG.debug(f"Cover already exists {comic_path} {db_cover_path}")
            return
        fs_cover_path.parent.mkdir(exist_ok=True, parents=True)

        if comic_path is None:
            comic_path = Comic.objects.only("path").get(cover_path=db_cover_path).path

        # Reopens the car, so slightly inefficient.
        car = ComicArchive(comic_path)
        im = Image.open(BytesIO(car.get_cover_image()))
        im.thumbnail(THUMBNAIL_SIZE)
        im.save(fs_cover_path, im.format)
        LOG.info(f"Created cover thumbnail for: {comic_path}")
        QUEUE.put(LibraryChangedTask())
    except Exception as exc:
        LOG.exception(exc)
        LOG.error(f"Failed to create cover thumb for {comic_path}")

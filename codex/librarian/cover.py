"""Functions for dealing with comic cover thumbnails."""
import logging

from io import BytesIO
from pathlib import Path

from comicbox.comic_archive import ComicArchive
from fnvhash import fnv1a_32
from PIL import Image

from codex.librarian.queue import QUEUE
from codex.librarian.queue import LibraryChangedTask
from codex.models import Comic
from codex.settings.settings import CONFIG_STATIC
from codex.settings.settings import STATIC_ROOT


THUMBNAIL_SIZE = (120, 180)


COVER_ROOT = Path(f"{CONFIG_STATIC}/covers")
MISSING_COVER_FN = "missing_cover.png"
BUILDING_COVER_FN = "building_cover.png"
MISSING_COVER_SRC = STATIC_ROOT / "img" / MISSING_COVER_FN
MISSING_COVER_FS_PATH = COVER_ROOT / MISSING_COVER_FN
HEX_FILL = 8
PATH_STEP = 2
LOG = logging.getLogger(__name__)


def cleanup_cover_dirs(path):
    """Recursively remove empty cover directories."""
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


def hex_path(comic_path):
    """Translate an integer into an efficient filesystem path."""
    fnv = fnv1a_32(bytes(str(comic_path), "utf-8"))
    hex_str = "{0:0{1}x}".format(fnv, HEX_FILL)
    parts = []
    for i in range(0, len(hex_str), PATH_STEP):
        parts.append(hex_str[i : i + PATH_STEP])
    path = Path("/".join(parts))
    return path


def get_cover_path(comic_path):
    """Get path to a cover image, creating the image if not found."""
    cover_path = hex_path(comic_path)
    return cover_path.with_suffix(".jpg")


def create_comic_cover(comic_path, db_cover_path, force=False):
    """Create a comic cover thumnail and save it to disk."""
    try:
        if db_cover_path == MISSING_COVER_FN and not force:
            LOG.debug(f"Cover for {comic_path} missing.")
            return

        fs_cover_path = COVER_ROOT / db_cover_path
        if fs_cover_path.exists() and not force:
            LOG.debug(f"Cover already exists {comic_path} {db_cover_path}")
            return
        fs_cover_path.parent.mkdir(exist_ok=True, parents=True)

        if comic_path is None:
            comic = Comic.objects.only("path").get(cover_path=db_cover_path)
            comic_path = comic.path

        # Reopens the car, so slightly inefficient.
        car = ComicArchive(comic_path)
        im = Image.open(BytesIO(car.get_cover_image()))
        im.thumbnail(THUMBNAIL_SIZE)
        im.save(fs_cover_path, im.format)
        LOG.info(f"Created cover thumbnail for: {comic_path}")
        QUEUE.put(LibraryChangedTask())
    except Exception as exc:
        LOG.error(f"Failed to create cover thumb for {comic_path}")
        LOG.exception(exc)
        Comic.objects.filter(comic_path=comic_path).update(cover_path=MISSING_COVER_FN)
        LOG.warn(f"Marked cover for {comic_path} missing.")

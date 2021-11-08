"""Functions for dealing with comic cover thumbnails."""
import time

from io import BytesIO
from logging import INFO, getLogger
from pathlib import Path

from comicbox.comic_archive import ComicArchive
from fnvhash import fnv1a_32
from PIL import Image

from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    BulkComicCoverCreateTask,
    ImageComicCoverCreateTask,
)
from codex.models import Comic, Library
from codex.settings.settings import CONFIG_STATIC, STATIC_ROOT
from codex.threads import QueuedThread


THUMBNAIL_SIZE = (120, 180)


COVER_ROOT = Path(f"{CONFIG_STATIC}/covers")
MISSING_COVER_FN = "missing_cover.png"
BUILDING_COVER_FN = "building_cover.png"
MISSING_COVER_SRC = STATIC_ROOT / "img" / MISSING_COVER_FN
MISSING_COVER_FS_PATH = COVER_ROOT / MISSING_COVER_FN
HEX_FILL = 8
PATH_STEP = 2
LOG = getLogger(__name__)
LOG_EVERY = 15


def _cleanup_cover_dirs(path):
    """Recursively remove empty cover directories."""
    if COVER_ROOT not in path.parents:
        return
    try:
        path.rmdir()
        _cleanup_cover_dirs(path.parent)
    except OSError:
        pass


def purge_cover(comic):
    """Remove one cover thumb from the filesystem."""
    if not comic or comic.cover_path:
        return
    cover_path = COVER_ROOT / comic.cover_path
    try:
        # XXX python 3.8 missing_ok=True
        # Switch to python 3.8 requirement begginning of 2021
        cover_path.unlink()
    except FileNotFoundError:
        pass
    _cleanup_cover_dirs(cover_path.parent)


def purge_cover_path(comic_cover_path):
    """Remove one cover thumb from the filesystem."""
    if not comic_cover_path:
        return
    cover_path = COVER_ROOT / comic_cover_path
    try:
        # XXX python 3.8 missing_ok=True
        # Switch to python 3.8 requirement begginning of 2021
        cover_path.unlink()
    except FileNotFoundError:
        pass
    _cleanup_cover_dirs(cover_path.parent)


def purge_all_covers(library):
    """Remove all cover thumbs for a library."""
    comics = Comic.objects.only("path", "library").filter(library=library)
    for comic in comics:
        purge_cover(comic)


def _hex_path(comic_path):
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
    cover_path = _hex_path(comic_path)
    return str(cover_path.with_suffix(".jpg"))


def _create_comic_cover(comic_path, cover_image, fs_cover_path):
    if cover_image is None:
        raise ValueError(f"No cover image found for {comic_path}")

    fs_cover_path.parent.mkdir(exist_ok=True, parents=True)

    im = Image.open(BytesIO(cover_image))
    im.thumbnail(THUMBNAIL_SIZE)
    im.save(fs_cover_path, im.format)
    LOG.debug(f"Created cover thumbnail for: {comic_path}")
    return 1


def _create_comic_cover_from_file(comic, force=False):
    """Create a comic cover thumnail and save it to disk."""
    # The browser sends x_path and x_comic_path, everything else sends no prefix
    count = 0
    cover_path = comic.get("x_cover_path", comic.get("cover_path"))
    comic_path = comic.get("x_path", comic.get("path"))
    try:
        fs_cover_path = COVER_ROOT / cover_path
        if (cover_path == MISSING_COVER_FN or fs_cover_path.exists()) and not force:
            return count

        if comic_path is None:
            comic_path = Comic.objects.get(cover_path=cover_path).path

        # Reopens the car, so slightly inefficient.
        cover_image = ComicArchive(comic_path).get_cover_image()
        count = _create_comic_cover(comic_path, cover_image, fs_cover_path)
    except Comic.DoesNotExist:
        LOG.warning(f"Comic for {cover_path=} does not exist in the db.")
    except Exception as exc:
        LOG.error(f"Failed to create cover thumb for {comic_path}")
        LOG.exception(exc)
        Comic.objects.filter(comic_path=comic_path).update(cover_path=MISSING_COVER_FN)
        LOG.warn(f"Marked cover for {comic_path} missing.")
    return count


def _bulk_create_comic_covers(comic_and_cover_paths, force=False):
    """Create bulk comic covers."""
    num_comics = len(comic_and_cover_paths)
    LOG.debug(f"Checking {num_comics} comic covers...")
    start_time = time.time()

    comic_counter = 0
    for comic in comic_and_cover_paths:
        comic_counter += _create_comic_cover_from_file(comic, force)
    elapsed = time.time() - start_time
    if comic_counter:
        per = elapsed / comic_counter
        suffix = f" at {per}s per cover"
    else:
        suffix = ""
    log_text = f"Created {comic_counter} comic covers in {elapsed}s{suffix}."
    if comic_counter:
        LOG.info(log_text)
    else:
        LOG.debug(log_text)
    return comic_counter


def regen_all_covers(library_pk):
    """Force regeneration of all covers."""
    if LOG.getEffectiveLevel() >= INFO:
        path = Library.objects.get(library_pk).path
        LOG.info(f"Recreating all comic covers for library {path}")
    comics = (
        Comic.objects.only("path", "library")
        .filter(library_id=library_pk)
        .values("path", "cover_path")
    )
    task = BulkComicCoverCreateTask(True, tuple(comics))
    LIBRARIAN_QUEUE.put(task)


class CoverCreator(QueuedThread):
    """Create comic covers in it's own thread."""

    NAME = "CoverCreator"

    def _process_item(self, task):
        """Run the creator."""
        if isinstance(task, BulkComicCoverCreateTask):
            _bulk_create_comic_covers(task.comics, task.force)
        elif isinstance(task, ImageComicCoverCreateTask):
            fs_cover_path = COVER_ROOT / task.cover_path
            _create_comic_cover(task.comic_path, task.image_data, fs_cover_path)
        else:
            LOG.error(f"Bad task sent to {self.NAME}: {task}")

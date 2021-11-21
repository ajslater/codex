"""Functions for dealing with comic cover thumbnails."""
import time

from io import BytesIO
from logging import INFO, getLogger
from pathlib import Path

from comicbox.comic_archive import ComicArchive
from django.db.models.functions import Now
from PIL import Image

from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    BulkComicCoverCreateTask,
    CreateComicCoversLibrariesTask,
    ImageComicCoverCreateTask,
    PurgeComicCoversLibrariesTask,
    PurgeComicCoversTask,
)
from codex.models import Comic, Library
from codex.settings.settings import CONFIG_STATIC
from codex.threads import QueuedThread


THUMBNAIL_SIZE = (120, 180)


COVER_ROOT = Path(f"{CONFIG_STATIC}/covers")
MISSING_COVER_FN = "missing_cover.png"
LOG = getLogger(__name__)


def _cleanup_cover_dirs(path):
    """Recursively remove empty cover directories."""
    if COVER_ROOT not in path.parents:
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
    try:
        # XXX python 3.8 missing_ok=True
        # Switch to python 3.8 requirement begginning of 2021
        cover_path.unlink()
    except FileNotFoundError:
        pass
    return cover_path.parent


def _purge_cover_paths(cover_paths):
    cover_dirs = set()
    for cover_path in cover_paths:
        cover_path_parent = _purge_cover_path(cover_path)
        cover_dirs.add(cover_path_parent)
    for cover_dir in cover_dirs:
        _cleanup_cover_dirs(cover_dir)


def _purge_library_covers(library_pks):
    """Remove all cover thumbs for a library."""
    cover_paths = Comic.objects.filter(library_id__in=library_pks).values_list(
        "cover_path", flat=True
    )
    _purge_cover_paths(cover_paths)


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
    missing = None
    cover_path = comic.get("x_cover_path", comic.get("cover_path"))
    comic_path = comic.get("x_path", comic.get("path"))
    if not comic_path and not cover_path:
        LOG.warning("Not creating comic cover for empty object.")
        return count, missing
    try:
        if not cover_path:
            cover_path = Comic.objects.get(path=comic_path).cover_path

        fs_cover_path = COVER_ROOT / cover_path
        if (cover_path == MISSING_COVER_FN or fs_cover_path.exists()) and not force:
            return count, missing

        if comic_path is None:
            comic_path = Comic.objects.get(cover_path=cover_path).path

        # Reopens the car, so slightly inefficient.
        cover_image = ComicArchive(comic_path).get_cover_image()
        count = _create_comic_cover(comic_path, cover_image, fs_cover_path)
    except Comic.DoesNotExist:
        LOG.warning(f"Comic for {cover_path=} does not exist in the db.")
    except Exception as exc:
        if isinstance(exc, FileNotFoundError):
            LOG.warning(f"Comic at {comic_path} not found.")
        else:
            LOG.exception(exc)
            LOG.error(f"Failed to create cover thumb for {comic_path}")
        missing = comic_path
    return count, missing


def _bulk_create_comic_covers(comic_and_cover_paths, force=False):
    """Create bulk comic covers."""
    num_comics = len(comic_and_cover_paths)
    LOG.debug(f"Checking {num_comics} comic covers...")
    start_time = time.time()

    # Create comics
    comic_counter = 0
    missing_cover_comic_paths = set()
    for comic in comic_and_cover_paths:
        count, missing = _create_comic_cover_from_file(comic, force)
        comic_counter += count
        if missing:
            missing_cover_comic_paths.add(missing)

    # Mark missing
    if missing_cover_comic_paths:
        count = Comic.objects.filter(path__in=missing_cover_comic_paths).update(
            cover_path=MISSING_COVER_FN, updated_at=Now()
        )
        LOG.warn(f"Marked covers for {count} comics missing.")

    elapsed = time.time() - start_time
    if comic_counter:
        per = elapsed / comic_counter
        suffix = f" at {per:.3f}s per cover"
    else:
        suffix = ""
    log_text = f"Created {comic_counter} comic covers in {elapsed:.1f}s{suffix}."
    if comic_counter:
        LOG.info(log_text)
    else:
        LOG.debug(log_text)
    return comic_counter


def _create_comic_cover_for_libraries(library_pks):
    """Force regeneration of all covers."""
    if LOG.getEffectiveLevel() >= INFO:
        paths = Library.objects.filter(pk__in=library_pks).values_list(
            "path", flat=True
        )
        LOG.info(f"Recreating all comic covers for libraries: {paths}")
    comics = (
        Comic.objects.only("path", "library")
        .filter(library_id__in=library_pks)
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
        elif isinstance(task, CreateComicCoversLibrariesTask):
            _create_comic_cover_for_libraries(task.library_ids)
        elif isinstance(task, PurgeComicCoversLibrariesTask):
            _purge_library_covers(task.library_ids)
        elif isinstance(task, PurgeComicCoversTask):
            _purge_cover_paths(task.cover_paths)
        else:
            LOG.error(f"Bad task sent to {self.NAME}: {task}")

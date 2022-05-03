"""Create comic cover paths."""
import os
import time

from io import BytesIO
from logging import INFO
from pathlib import Path

from comicbox.comic_archive import ComicArchive
from django.db.models.functions import Now
from fnvhash import fnv1a_32
from humanize import naturalsize
from PIL import Image

from codex.librarian.covers import COVER_ROOT
from codex.librarian.covers.purge import purge_cover_paths
from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    BroadcastNotifierTask,
    BulkComicCoverCreateTask,
)
from codex.models import Comic, Library
from codex.pdf import PDF
from codex.settings.logging import get_logger
from codex.version import COMICBOX_CONFIG


THUMBNAIL_SIZE = (120, 180)
MISSING_COVER_FN = "missing_cover.webp"
BULK_UPDATE_COMIC_COVER_FIELDS = ("cover_path", "updated_at")
COVER_DB_UPDATE_INTERVAL = 10
HEX_FILL = 8
PATH_STEP = 2
LOG = get_logger(__name__)
LOG_RSS = bool(os.getenv("LOG_COVER_RSS"))
if LOG_RSS:
    import psutil


def _hex_path(comic_path):
    """Translate an integer into an efficient filesystem path."""
    fnv = fnv1a_32(bytes(str(comic_path), "utf-8"))
    hex_str = "{0:0{1}x}".format(fnv, HEX_FILL)
    parts = []
    for i in range(0, len(hex_str), PATH_STEP):
        parts.append(hex_str[i : i + PATH_STEP])
    path = Path("/".join(parts))
    return path


def _get_cover_path(comic_path):
    """Get path to a cover image, creating the image if not found."""
    cover_path = _hex_path(comic_path)
    return str(cover_path.with_suffix(".webp"))


def _save_thumbnail(image_data, fs_cover_path):
    """Isolate the save thumbnail function for leak detection."""
    with BytesIO(image_data) as image_io:
        with Image.open(image_io) as cover_image:
            cover_image.thumbnail(
                THUMBNAIL_SIZE,
                Image.Resampling.LANCZOS,  # type: ignore
                reducing_gap=3.0,
            )
            cover_image.save(
                fs_cover_path, "WEBP", lossless=False, quality=100, method=6
            )
    cover_image.close()  # extra close for animated sequences


def create_comic_cover(comic_path, image_data, cover_path=None):
    """Create a comic cover from an image."""
    try:
        if image_data is None:
            raise ValueError(f"No cover image found for {comic_path}")

        if not cover_path:
            cover_path = _get_cover_path(comic_path)

        fs_cover_path = COVER_ROOT / cover_path
        fs_cover_path.parent.mkdir(exist_ok=True, parents=True)

        _save_thumbnail(image_data, fs_cover_path)

        LOG.debug(f"Created cover thumbnail for: {comic_path}")
        update_cover_path = cover_path
    except Exception as exc:
        LOG.warning(f"Failed to create cover thumb for {comic_path}: {exc}")
        update_cover_path = MISSING_COVER_FN
    return update_cover_path


def _create_comic_cover_from_file(comic, force=False):
    """Create a comic cover thumnail and save it to disk."""
    update_cover_path = None
    try:
        correct_cover_path = _get_cover_path(comic.path)
        fs_cover_path = COVER_ROOT / correct_cover_path
        if not force and fs_cover_path.exists():
            if correct_cover_path != comic.cover_path:
                update_cover_path = correct_cover_path
        else:
            if comic.file_format == Comic.FileFormats.PDF:
                car_class = PDF
            else:
                car_class = ComicArchive
            with car_class(comic.path, config=COMICBOX_CONFIG) as car:
                cover_image = car.get_cover_image()
            update_cover_path = create_comic_cover(
                comic.path, cover_image, correct_cover_path
            )
    except OSError as exc:
        LOG.warning(f"Failed to create cover thumb for {comic.path}: {exc}")
        update_cover_path = MISSING_COVER_FN
    except Exception as exc:
        LOG.error(f"Failed to create cover thumb for {comic.path}")
        LOG.exception(exc)
        update_cover_path = MISSING_COVER_FN
    return update_cover_path


def _bulk_update_comic_covers_db(update_comics, covers_created_count, num_comics):
    now = Now()
    for comic in update_comics:
        comic.updated_at = now

    batch_count = Comic.objects.bulk_update(
        update_comics, BULK_UPDATE_COMIC_COVER_FIELDS
    )
    if batch_count:
        LIBRARIAN_QUEUE.put(BroadcastNotifierTask("LIBRARY_CHANGED"))
    else:
        batch_count = 0
    LOG.info("Created covers for " f"{covers_created_count}/{num_comics} comics.")
    return batch_count


def _log_rss(rss):
    """Log rss stats."""
    log_str = "Cover RSS"
    for key, val in rss.items():
        if key == "process":
            continue
        log_str += f" {key}: {naturalsize(val)}"
    LOG.verbose(log_str)


def _init_rss():
    """Initialize the rss dict."""
    rss = {
        "process": psutil.Process(os.getpid()),
    }
    rss["start"] = rss["process"].memory_info().rss
    rss["peak"] = rss["start"]
    rss["now"] = rss["start"]
    _log_rss(rss)
    return rss


def _log_bulk_create_results(start_time, count, rss):
    """Log results of the bulk create."""
    elapsed = time.time() - start_time
    if count:
        per = elapsed / count
        suffix = f" at {per:.3f}s per cover"
    else:
        suffix = ""
    log_text = f"Created {count} comic covers in {elapsed:.1f}s{suffix}."
    if count:
        LOG.info(log_text)
    else:
        LOG.debug(log_text)

    if LOG_RSS:
        rss["process"].memory_info().rss  # type: ignore
        _log_rss(rss)


def bulk_create_comic_covers(comic_pks, force=False):
    """Create bulk comic covers."""
    num_comics = len(comic_pks)
    if not num_comics:
        return

    LOG.verbose(f"Checking {num_comics} comic covers...")
    start_time = time.time()

    if LOG_RSS:
        rss = _init_rss()
    else:
        rss = {}

    # Get comic objects
    count = 0
    last_db_update = time.time()
    covers_created_count = 0
    update_comics = []
    purge_cps = set()
    comics = Comic.objects.filter(pk__in=comic_pks).only("path", "cover_path")

    for comic in comics:
        # Create all covers.
        update_cover_path = _create_comic_cover_from_file(comic, force)
        if not update_cover_path:
            continue
        if comic.cover_path not in (MISSING_COVER_FN, update_cover_path):
            purge_cps.add(comic.cover_path)
        comic.cover_path = update_cover_path
        update_comics.append(comic)
        covers_created_count += 1

        if LOG_RSS:
            rss["now"] = rss["process"].memory_info().rss  # type: ignore
            if rss["now"] > rss["peak"]:
                rss["peak"] = rss["now"]

        # Update batches of comics in the db and notify the frontend every
        # 10 seconds
        elapsed = time.time() - last_db_update
        if elapsed > COVER_DB_UPDATE_INTERVAL:
            batch_update_comics = update_comics
            update_comics = []
            count += _bulk_update_comic_covers_db(
                batch_update_comics, covers_created_count, num_comics
            )
            if LOG_RSS:
                _log_rss(rss)
            last_db_update = time.time()

    # Finish
    count += _bulk_update_comic_covers_db(
        update_comics, covers_created_count, num_comics
    )
    purge_cover_paths(purge_cps)
    _log_bulk_create_results(start_time, count, rss)
    return count


def create_comic_cover_for_libraries(library_pks):
    """Force regeneration of all covers."""
    if LOG.getEffectiveLevel() <= INFO:
        paths = Library.objects.filter(pk__in=library_pks).values_list(
            "path", flat=True
        )
        paths_str = ",".join(paths)
        LOG.info(f"Recreating all comic covers for libraries: {paths_str}")
    comic_pks = Comic.objects.filter(library_id__in=library_pks).values_list(
        "pk", flat=True
    )
    task = BulkComicCoverCreateTask(True, tuple(comic_pks))
    LIBRARIAN_QUEUE.put(task)


def create_missing_covers():
    """Generate covers for comics missing covers."""
    comics_with_covers = Comic.objects.all().only("cover_path")
    no_cover_comic_pks = set()
    for comic in comics_with_covers:
        if not comic.cover_path or Path(comic.cover_path).exists():
            no_cover_comic_pks.add(comic.pk)

    no_cover_comic_pks = tuple(no_cover_comic_pks)
    LOG.verbose(f"Generating covers for {len(no_cover_comic_pks)} comics missing them.")
    task = BulkComicCoverCreateTask(True, no_cover_comic_pks)
    LIBRARIAN_QUEUE.put(task)

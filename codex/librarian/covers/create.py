"""Create comic cover paths."""
import os
import time

from io import BytesIO
from logging import INFO
from pathlib import Path

import psutil

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
    cover_image = None
    try:
        if image_data is None:
            raise ValueError(f"No cover image found for {comic_path}")

        if not cover_path:
            cover_path = _get_cover_path(comic_path)

        fs_cover_path = COVER_ROOT / cover_path
        fs_cover_path.parent.mkdir(exist_ok=True, parents=True)

        args = (image_data, fs_cover_path)
        _save_thumbnail(*args)

        LOG.debug(f"Created cover thumbnail for: {comic_path}")
        update_cover_path = cover_path
    except Exception as exc:
        LOG.warning(f"Failed to create cover thumb for {comic_path}: {exc}")
        LOG.exception(exc)
        update_cover_path = MISSING_COVER_FN
    finally:
        if cover_image:
            cover_image.close()
    return update_cover_path


def _create_comic_cover_from_file(comic, force=False):
    """Create a comic cover thumnail and save it to disk."""
    car = None
    update_cover_path = None
    try:
        correct_cover_path = _get_cover_path(comic.path)
        fs_cover_path = COVER_ROOT / correct_cover_path
        if not force and fs_cover_path.exists():
            if correct_cover_path != comic.cover_path:
                update_cover_path = correct_cover_path
        else:
            if comic.file_format == Comic.FileFormats.PDF:
                car_cls = PDF
            else:
                car_cls = ComicArchive
            with car_cls(comic.path, config=COMICBOX_CONFIG) as car:
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
    finally:
        if car:
            car.close()
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


def bulk_create_comic_covers(comic_pks, force=False):
    """Create bulk comic covers."""
    num_comics = len(comic_pks)
    if not num_comics:
        return

    LOG.verbose(f"Checking {num_comics} comic covers...")
    start_time = time.time()

    log_rss = bool(os.getenv("COVER_RSS"))
    if log_rss:
        process = psutil.Process(os.getpid())
        start_rss = process.memory_info().rss
        LOG.verbose(f"Cover RSS: {naturalsize(start_rss)}")
        peak_rss = start_rss

    count = 0
    last_db_update = time.time()
    covers_created_count = 0
    update_comics = []
    purge_cps = set()
    comics = Comic.objects.filter(pk__in=comic_pks).only("pk", "path", "cover_path")

    for comic in comics:
        update_cover_path = _create_comic_cover_from_file(comic, force)
        if not update_cover_path:
            continue
        if comic.cover_path not in (MISSING_COVER_FN, update_cover_path):
            purge_cps.add(comic.cover_path)
        comic.cover_path = update_cover_path
        update_comics.append(comic)
        covers_created_count += 1

        if log_rss:
            rss = process.memory_info().rss  # type: ignore
            if rss > peak_rss:  # type: ignore
                peak_rss = rss

        # Update batches of comics in the db and notify the frontend every
        # COVER_DB_UPDATE_INTERVAL seconds
        elapsed = time.time() - last_db_update
        if elapsed > COVER_DB_UPDATE_INTERVAL:
            batch_update_comics = update_comics
            update_comics = []
            count += _bulk_update_comic_covers_db(
                batch_update_comics, covers_created_count, num_comics
            )
            if log_rss:
                LOG.verbose(
                    f"Cover RSS start: {naturalsize(start_rss)} "  # type: ignore
                    f"peak: {naturalsize(peak_rss)} "  # type: ignore
                    f"now: {naturalsize(rss)}"  # type: ignore
                )
            last_db_update = time.time()
    count += _bulk_update_comic_covers_db(
        update_comics, covers_created_count, num_comics
    )
    purge_cover_paths(purge_cps)

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
    comics = update_comics = purge_cps = None
    if log_rss:
        rss = process.memory_info().rss  # type: ignore
        LOG.verbose(
            f"Cover RSS start: {naturalsize(start_rss)} "  # type: ignore
            f"peak: {naturalsize(peak_rss)} "  # type: ignore
            f"finish: {naturalsize(rss)}"  # type:ignore
        )
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

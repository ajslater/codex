"""Create comic cover paths."""
import time

from io import BytesIO
from logging import INFO, getLogger

from comicbox.comic_archive import ComicArchive
from django.db.models.functions import Now
from PIL import Image

from codex.librarian.covers import COVER_ROOT
from codex.librarian.queue_mp import LIBRARIAN_QUEUE, BulkComicCoverCreateTask
from codex.models import Comic, Library
from codex.serializers.mixins import UNIONFIX_PREFIX


THUMBNAIL_SIZE = (120, 180)
MISSING_COVER_FN = "missing_cover.png"
LOG = getLogger(__name__)


def create_comic_cover(comic_path, cover_image, cover_path):
    """Create a comic cover from an image."""
    if cover_image is None:
        raise ValueError(f"No cover image found for {comic_path}")

    fs_cover_path = COVER_ROOT / cover_path
    fs_cover_path.parent.mkdir(exist_ok=True, parents=True)

    im = Image.open(BytesIO(cover_image))
    im.thumbnail(THUMBNAIL_SIZE)
    im.save(fs_cover_path, im.format)
    LOG.debug(f"Created cover thumbnail for: {comic_path}")
    return 1


def _create_comic_cover_from_file(comic_path, cover_path, force=False):
    """Create a comic cover thumnail and save it to disk."""
    count = 0
    missing = None

    try:
        if not force:
            fs_cover_path = COVER_ROOT / cover_path
            if cover_path == MISSING_COVER_FN or fs_cover_path.exists():
                return count, missing

        # Reopens the car, so slightly inefficient.
        cover_image = ComicArchive(comic_path).get_cover_image()
        count = create_comic_cover(comic_path, cover_image, cover_path)
    except Comic.DoesNotExist:
        LOG.warning(f"Comic for {cover_path=} does not exist in the db.")
    except FileNotFoundError:
        LOG.warning(f"Comic at {comic_path} not found.")
        missing = comic_path
    except Exception as exc:
        LOG.exception(exc)
        LOG.error(f"Failed to create cover thumb for {comic_path}")
        missing = comic_path
    return count, missing


def _get_comic_and_cover_paths(paths_only_set, field_name):
    """Query the database in bulk for missing fields."""
    if not paths_only_set:
        return set()

    filter = {f"{field_name}__in": paths_only_set}
    comic_tuples = Comic.objects.filter(**filter).values_list("path", "cover_path")
    return set(comic_tuples)


def _ensure_comic_and_cover_paths(comic_and_cover_paths):
    """Ensure path and cover_path exist from partial data."""
    complete_comic_tuples = set()
    comic_paths_only = set()
    cover_paths_only = set()
    for comic_dict in comic_and_cover_paths:
        cover_path = comic_dict.get(
            f"{UNIONFIX_PREFIX}cover_path", comic_dict.get("cover_path")
        )
        comic_path = comic_dict.get("path")

        if comic_path and cover_path:
            complete_comic_tuples.add((comic_path, cover_path))
        elif comic_path and not cover_path:
            comic_paths_only.add(comic_path)
        elif not comic_path and cover_path:
            cover_paths_only.add(cover_path)
        else:
            LOG.warning("Not creating comic cover for empty object.")

    complete_comic_tuples |= _get_comic_and_cover_paths(comic_paths_only, "path")
    complete_comic_tuples |= _get_comic_and_cover_paths(cover_paths_only, "cover_path")

    return complete_comic_tuples


def bulk_create_comic_covers(comic_and_cover_paths, force=False):
    """Create bulk comic covers."""
    num_comics = len(comic_and_cover_paths)
    LOG.debug(f"Checking {num_comics} comic covers...")
    start_time = time.time()

    comic_tuples = _ensure_comic_and_cover_paths(comic_and_cover_paths)

    # Create comics
    comic_counter = 0
    missing_cover_comic_paths = set()
    for path, cover_path in comic_tuples:
        count, missing = _create_comic_cover_from_file(path, cover_path, force)
        comic_counter += count
        if missing:
            missing_cover_comic_paths.add(missing)

    # Mark missing
    if missing_cover_comic_paths:
        count = Comic.objects.filter(path__in=missing_cover_comic_paths).update(
            cover_path=MISSING_COVER_FN, updated_at=Now()
        )
        LOG.warning(f"Marked covers for {count} comics missing.")

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


def create_comic_cover_for_libraries(library_pks):
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

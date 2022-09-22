"""Create comic cover paths."""
import time

from io import BytesIO

from comicbox.comic_archive import ComicArchive
from humanize import naturaldelta
from PIL import Image

from codex.librarian.covers.path import MISSING_COVER_PATH, get_cover_path
from codex.librarian.covers.status import CoverStatusTypes
from codex.librarian.covers.tasks import CoverCreateTask
from codex.librarian.status_control import StatusControl
from codex.models import Comic
from codex.pdf import PDF
from codex.settings.logging import get_logger
from codex.version import COMICBOX_CONFIG


_COVER_RATIO = 1.5372233400402415  # modal cover ratio
_THUMBNAIL_WIDTH = 165
_THUMBNAIL_HEIGHT = round(_THUMBNAIL_WIDTH * _COVER_RATIO)
_THUMBNAIL_SIZE = (_THUMBNAIL_WIDTH, _THUMBNAIL_HEIGHT)
_COVER_DB_UPDATE_INTERVAL = 10

LOG = get_logger(__name__)


def _create_cover_thumbnail(cover_image_data):
    """Isolate the save thumbnail function for leak detection."""
    with BytesIO() as cover_thumb_buffer:
        with BytesIO(cover_image_data) as image_io:
            with Image.open(image_io) as cover_image:
                cover_image.thumbnail(
                    _THUMBNAIL_SIZE,
                    Image.Resampling.LANCZOS,  # type: ignore
                    reducing_gap=3.0,
                )
                cover_image.save(cover_thumb_buffer, "WEBP", method=6)
            cover_image.close()  # extra close for animated sequences
        thumb_image_data = cover_thumb_buffer.getvalue()
    return thumb_image_data


def create_cover(pk, cover_path):
    """
    Create comic cover if none exists.

    Return image thumb data or path to missing file thumb.
    """
    thumb_image_data = None
    comic = Comic.objects.only("path", "file_format").get(pk=pk)
    try:
        if comic.file_format == Comic.FileFormat.PDF:
            car_class = PDF
        else:
            car_class = ComicArchive
        with car_class(comic.path, config=COMICBOX_CONFIG) as car:
            image_data = car.get_cover_image()
        if not image_data:
            raise ValueError("Read empty cover.")
        thumb_image_data = _create_cover_thumbnail(image_data)
        task = CoverCreateTask(cover_path, thumb_image_data)
    except Exception as exc:
        LOG.warning(f"Could not create cover thumbnail for {comic.path}: {exc}")
        task = CoverCreateTask(cover_path, bytes())
    return task


def create_comic_cover(cover_path, data):
    """Save image data to a cover path."""
    cover_path.parent.mkdir(exist_ok=True, parents=True)
    if data:
        with cover_path.open("wb") as cover_file:
            cover_file.write(data)
    else:
        cover_path.symlink_to(MISSING_COVER_PATH)


def bulk_create_comic_covers(comic_pks):
    """Create bulk comic covers."""
    try:
        num_comics = len(comic_pks)
        if not num_comics:
            return

        LOG.verbose(f"Creating {num_comics} comic covers...")
        StatusControl.start(CoverStatusTypes.CREATE, num_comics)

        # Get comic objects
        count = 0
        last_update = start_time = time.time()

        for pk in comic_pks:
            # Create all covers.
            cover_path = get_cover_path(pk)
            if cover_path.exists():
                num_comics -= 1
            else:
                task = create_cover(pk, cover_path)
                # bulk creator creates covers inline
                create_comic_cover(task.path, task.data)
                count += 1

            # notify the frontend every 10 seconds
            elapsed = time.time() - last_update
            if elapsed > _COVER_DB_UPDATE_INTERVAL:
                LOG.verbose(f"Created {count}/{num_comics} comic covers.")
                StatusControl.update(CoverStatusTypes.CREATE, count, num_comics)
                last_update = time.time()

        total_elapsed = naturaldelta(time.time() - start_time)
        LOG.verbose(f"Created {count} comic covers in {total_elapsed}.")
        return count
    finally:
        StatusControl.finish(CoverStatusTypes.CREATE)

"""Create comic cover paths."""
import time

from datetime import datetime
from io import BytesIO

from comicbox.comic_archive import ComicArchive
from humanize import naturaldelta
from PIL import Image

from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.covers.status import CoverStatusTypes
from codex.models import Comic
from codex.pdf import PDF
from codex.version import COMICBOX_CONFIG


class CoverCreateMixin(CoverPathMixin):
    """Create methods for covers."""

    _COVER_RATIO = 1.5372233400402415  # modal cover ratio
    _THUMBNAIL_WIDTH = 165
    _THUMBNAIL_HEIGHT = round(_THUMBNAIL_WIDTH * _COVER_RATIO)
    _THUMBNAIL_SIZE = (_THUMBNAIL_WIDTH, _THUMBNAIL_HEIGHT)

    @classmethod
    def _create_cover_thumbnail(cls, cover_image_data):
        """Isolate the save thumbnail function for leak detection."""
        with BytesIO() as cover_thumb_buffer:
            with BytesIO(cover_image_data) as image_io:
                with Image.open(image_io) as cover_image:
                    cover_image.thumbnail(
                        cls._THUMBNAIL_SIZE,
                        Image.Resampling.LANCZOS,  # type: ignore
                        reducing_gap=3.0,
                    )
                    cover_image.save(cover_thumb_buffer, "WEBP", method=6)
                cover_image.close()  # extra close for animated sequences
            thumb_image_data = cover_thumb_buffer.getvalue()
        return thumb_image_data

    def create_cover(self, pk):
        """
        Create comic cover if none exists.

        Return image thumb data or path to missing file thumb.
        """
        thumb_image_data = None
        comic_path = None
        try:
            comic = Comic.objects.only("path", "file_format").get(pk=pk)
            comic_path = comic.path
            if comic.file_format == Comic.FileFormat.PDF:
                car_class = PDF
            else:
                car_class = ComicArchive
            with car_class(comic.path, config=COMICBOX_CONFIG) as car:
                image_data = car.get_cover_image()
            if not image_data:
                raise ValueError("Read empty cover.")
            thumb_image_data = self._create_cover_thumbnail(image_data)
        except Exception as exc:
            if not comic_path:
                comic_path = f"{pk=}"
            thumb_image_data = bytes()
            self.log.warning(
                f"Could not create cover thumbnail for {comic_path}: {exc}"
            )
        return thumb_image_data

    def create_comic_cover(self, cover_path, data):
        """Save image data to a cover path."""
        cover_path.parent.mkdir(exist_ok=True, parents=True)
        if data:
            with cover_path.open("wb") as cover_file:
                cover_file.write(data)
        else:
            cover_path.symlink_to(self.MISSING_COVER_PATH)

    def new_create_cover(self, pk):
        """Create a cover from a comic id."""
        start = time.time()
        cover_path = self.get_cover_path(pk)
        data = self.create_cover(pk)
        self.create_comic_cover(cover_path, data)
        elapsed = time.time() - start
        print(f"CREATED {pk} in {elapsed} seconds")

    def bulk_create_comic_covers(self, comic_pks):
        """Create bulk comic covers."""
        try:
            num_comics = len(comic_pks)
            if not num_comics:
                return

            self.log.debug(f"Creating {num_comics} comic covers...")
            self.status_controller.start(CoverStatusTypes.CREATE, num_comics)

            # Get comic objects
            count = 0
            start_time = since = datetime.now()

            for pk in comic_pks:
                # Create all covers.
                cover_path = self.get_cover_path(pk)
                if cover_path.exists():
                    num_comics -= 1
                else:
                    # bulk creator creates covers inline
                    self.new_create_cover(pk)
                    count += 1

                # notify the frontend every 10 seconds
                since = self.status_controller.update(
                    CoverStatusTypes.CREATE, count, num_comics, since=since
                )

            total_elapsed = naturaldelta(datetime.now() - start_time)
            self.log.info(f"Created {count} comic covers in {total_elapsed}.")
            return count
        finally:
            self.status_controller.finish(CoverStatusTypes.CREATE)

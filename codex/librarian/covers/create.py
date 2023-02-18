"""Create comic cover paths."""
from io import BytesIO
from time import time

from comicbox.comic_archive import ComicArchive
from humanize import naturaldelta
from PIL import Image

from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.covers.status import CoverStatusTypes
from codex.librarian.covers.tasks import CoverSaveToCache
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

    @classmethod
    def _get_comic_cover_image(cls, comic):
        """Create comic cover if none exists.

        Return image thumb data or path to missing file thumb.
        """
        if comic.file_format == Comic.FileFormat.PDF:
            car_class = PDF
        else:
            car_class = ComicArchive
        with car_class(comic.path, config=COMICBOX_CONFIG) as car:
            image_data = car.get_cover_image()
        if not image_data:
            raise ValueError("Read empty cover.")
        return image_data

    @classmethod
    def create_cover_from_path(cls, pk, cover_path, log, librarian_queue):
        """Create cover for path.

        Called from views/cover.
        """
        comic = None
        try:
            comic = Comic.objects.only("path", "file_format").get(pk=pk)
            cover_image = cls._get_comic_cover_image(comic)
            data = cls._create_cover_thumbnail(cover_image)
        except Exception as exc:
            data = bytes()
            comic_str = comic.path if comic else f"{pk=}"
            log.warning(f"Could not create cover thumbnail for {comic_str}: {exc}")

        task = CoverSaveToCache(cover_path, data)
        librarian_queue.put(task)
        return data

    def save_cover_to_cache(self, cover_path, data):
        """Save cover thumb image to the disk cache."""
        cover_path.parent.mkdir(exist_ok=True, parents=True)
        if data:
            with cover_path.open("wb") as cover_file:
                cover_file.write(data)
        else:
            cover_path.symlink_to(self.MISSING_COVER_PATH)

    #####################
    # UNUSED BELOW HERE #
    #####################

    def create_cover(self, pk):
        """Create a cover from a comic id."""
        # XXX Unused.
        cover_path = self.get_cover_path(pk)
        self.create_cover_from_path(pk, cover_path, self.log, self.librarian_queue)

    def bulk_create_comic_covers(self, comic_pks):
        """Create bulk comic covers."""
        # XXX Unused
        try:
            num_comics = len(comic_pks)
            if not num_comics:
                return

            self.log.debug(f"Creating {num_comics} comic covers...")
            self.status_controller.start(CoverStatusTypes.CREATE, num_comics)

            # Get comic objects
            count = 0
            start_time = since = time()

            for pk in comic_pks:
                # Create all covers.
                cover_path = self.get_cover_path(pk)
                if cover_path.exists():
                    num_comics -= 1
                else:
                    # bulk creator creates covers inline
                    self.create_cover(pk)
                    count += 1

                # notify the frontend every 10 seconds
                since = self.status_controller.update(
                    CoverStatusTypes.CREATE, count, num_comics, since=since
                )

            total_elapsed = naturaldelta(time() - start_time)
            self.log.info(f"Created {count} comic covers in {total_elapsed}.")
            return count
        finally:
            self.status_controller.finish(CoverStatusTypes.CREATE)

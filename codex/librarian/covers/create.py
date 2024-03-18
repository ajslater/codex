"""Create comic cover paths."""

from io import BytesIO
from time import time

from comicbox.box import Comicbox
from humanize import naturaldelta
from PIL import Image

from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.covers.status import CoverStatusTypes
from codex.librarian.covers.tasks import CoverSaveToCache
from codex.models import Comic
from codex.status import Status


class CoverCreateMixin(CoverPathMixin):
    """Create methods for covers."""

    _COVER_RATIO = 1.5372233400402415  # modal cover ratio
    THUMBNAIL_WIDTH = 165
    THUMBNAIL_HEIGHT = round(THUMBNAIL_WIDTH * _COVER_RATIO)
    _THUMBNAIL_SIZE = (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)

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
            return cover_thumb_buffer.getvalue()

    @classmethod
    def _get_comic_cover_image(cls, comic_path):
        """Create comic cover if none exists.

        Return image thumb data or path to missing file thumb.
        """
        with Comicbox(comic_path) as cb:
            image_data = cb.get_cover_image()
        if not image_data:
            reason = "Read empty cover"
            raise ValueError(reason)
        return image_data

    @classmethod
    def create_cover_from_path(cls, pk, cover_path, log, librarian_queue):
        """Create cover for path.

        Called from views/cover.
        """
        comic_path = None
        try:
            comic_path = Comic.objects.only("path").get(pk=pk).path
            cover_image = cls._get_comic_cover_image(comic_path)
            data = cls._create_cover_thumbnail(cover_image)
        except Exception as exc:
            data = b""
            comic_str = comic_path if comic_path else f"{pk=}"
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
        elif not cover_path.exists():
            cover_path.symlink_to(self.MISSING_COVER_PATH)

    def _bulk_create_comic_covers(self, comic_pks):
        """Create bulk comic covers."""
        num_comics = len(comic_pks)
        if not num_comics:
            return None
        status = Status(CoverStatusTypes.CREATE_COVERS, 0, num_comics)
        try:
            start_time = time()
            self.log.debug(f"Creating {num_comics} comic covers...")
            self.status_controller.start(status)

            # Get comic objects
            for pk in comic_pks:
                # Create all covers.
                cover_path = self.get_cover_path(pk)
                if cover_path.exists():
                    status.decrement_total()
                else:
                    # bulk contributor creates covers inline
                    self.create_cover_from_path(
                        pk, cover_path, self.log, self.librarian_queue
                    )
                    status.increment_complete()
                self.status_controller.update(status)

            total_elapsed = naturaldelta(time() - start_time)
            self.log.info(f"Created {status.complete} comic covers in {total_elapsed}.")
        finally:
            self.status_controller.finish(status)
        return status.complete

    def create_all_covers(self):
        """Create all covers for all libraries."""
        pks = Comic.objects.values_list("pk", flat=True)
        self._bulk_create_comic_covers(pks)

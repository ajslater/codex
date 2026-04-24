"""Create comic cover paths."""

import os
from abc import ABC
from io import BytesIO
from multiprocessing.queues import Queue
from pathlib import Path
from time import time

from comicbox.box import Comicbox
from humanize import naturaldelta
from PIL import Image

from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.covers.status import CreateCoversStatus
from codex.librarian.covers.tasks import CoverSaveToCache
from codex.librarian.status import Status
from codex.librarian.threads import QueuedThread
from codex.models import Comic, CustomCover
from codex.settings import COMICBOX_CONFIG

_PID = os.getpid()
_COVER_RATIO = 1.5372233400402415  # modal cover ratio
THUMBNAIL_WIDTH = 165
THUMBNAIL_HEIGHT = round(THUMBNAIL_WIDTH * _COVER_RATIO)
_THUMBNAIL_SIZE = (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)


class CoverCreateThread(QueuedThread, CoverPathMixin, ABC):
    """Create methods for covers."""

    @classmethod
    def _create_cover_thumbnail(cls, cover_image_data) -> BytesIO:
        """Isolate the save thumbnail function for leak detection."""
        cover_thumb_buffer = BytesIO()
        with BytesIO(cover_image_data) as image_io:
            with Image.open(image_io) as cover_image:
                cover_image.thumbnail(
                    _THUMBNAIL_SIZE,
                    Image.Resampling.LANCZOS,
                    reducing_gap=3.0,
                )
                cover_image.save(cover_thumb_buffer, "WEBP", method=6)
            cover_image.close()  # extra close for animated sequences
        return cover_thumb_buffer

    @classmethod
    def _get_comic_cover_image(cls, comic_path, log):
        """
        Create comic cover if none exists.

        Return image thumb data or path to missing file thumb.
        """
        with Comicbox(comic_path, config=COMICBOX_CONFIG, logger=log) as car:
            image_data = car.get_cover_page(pdf_format="pixmap")
        if not image_data:
            reason = "Read empty cover"
            raise ValueError(reason)
        return image_data

    @classmethod
    def _get_custom_cover_image(cls, cover_path):
        """Get cover image from image file."""
        with Path(cover_path).open("rb") as f:
            return f.read()

    @classmethod
    def create_cover_from_path(
        cls, pk: int, cover_path: str, log, librarian_queue: Queue, *, custom: bool
    ) -> BytesIO | None:
        """
        Create cover for path.

        Called from views/cover.
        """
        db_path = None
        try:
            model = CustomCover if custom else Comic
            db_path = model.objects.only("path").get(pk=pk).path
            if custom:
                cover_image = cls._get_custom_cover_image(db_path)
            else:
                cover_image = cls._get_comic_cover_image(db_path, log)
            thumb_buffer = cls._create_cover_thumbnail(cover_image)
            thumb_bytes = thumb_buffer.getvalue()
            thumb_buffer.seek(0)
        except Exception as exc:
            thumb_bytes = b""
            thumb_buffer = None
            cover_str = db_path or f"{pk=}"
            log.warning(f"Could not create cover thumbnail for {cover_str}: {exc}")

        task = CoverSaveToCache(cover_path, thumb_bytes)
        librarian_queue.put(task)
        return thumb_buffer

    def save_cover_to_cache(self, cover_path_str: str, data) -> None:
        """Save cover thumb image to the disk cache."""
        cover_path = Path(cover_path_str)
        cover_path.parent.mkdir(exist_ok=True, parents=True)
        if data:
            # Atomic write: stage to a sibling tmp file, then os.replace so
            # readers only ever observe the pre-existing state or the fully
            # written new file — never a half-written one.
            tmp_path = cover_path.with_name(f"{cover_path.name}.{_PID}.tmp")
            try:
                with tmp_path.open("wb") as cover_file:
                    cover_file.write(data)
                tmp_path.replace(cover_path)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise
        elif not cover_path.exists():
            # zero length file is code for missing.
            cover_path.touch()

    def _bulk_create_comic_cover(
        self, pk: int, status: Status, *, custom: bool
    ) -> None:
        # Create one cover
        cover_path = self.get_cover_path(pk, custom=custom)
        if cover_path.exists():
            status.decrement_total()
        else:
            # bulk credit creates covers inline
            data = self.create_cover_from_path(
                pk,
                str(cover_path),
                self.log,
                self.librarian_queue,
                custom=custom,
            )
            if data:
                data.close()
            status.increment_complete()
        self.status_controller.update(status)

    def _bulk_create_comic_covers(self, pks, *, custom: bool) -> int:
        """Create bulk comic covers."""
        num_comics = len(pks)
        if not num_comics:
            return 0
        status = CreateCoversStatus(0, num_comics)
        try:
            start_time = time()
            self.log.debug(f"Creating {num_comics} comic covers...")
            self.status_controller.start(status)
            for pk in pks:
                # Create all covers.
                self._bulk_create_comic_cover(pk, status, custom=custom)
            desc = "custom" if custom else "comic"
            count = status.complete
            level = "INFO" if count else "DEBUG"
            elapsed = naturaldelta(time() - start_time)
            self.log.log(level, f"Created {count} {desc} covers in {elapsed}.")
        finally:
            self.status_controller.finish(status)
        return status.complete or 0

    def create_all_covers(self) -> None:
        """Create all covers for all libraries."""
        pks = CustomCover.objects.values_list("pk", flat=True)
        count = self._bulk_create_comic_covers(pks, custom=True)
        pks = Comic.objects.values_list("pk", flat=True)
        count += self._bulk_create_comic_covers(pks, custom=False)

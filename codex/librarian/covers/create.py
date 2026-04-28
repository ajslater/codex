"""Create comic cover paths."""

import contextlib
import os
from abc import ABC
from collections.abc import Collection
from concurrent.futures import ProcessPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from time import time
from typing import override

from comicbox.box import Comicbox
from humanize import naturaldelta
from PIL import Image

from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.covers.status import CreateCoversStatus
from codex.librarian.threads import QueuedThread
from codex.models import Comic, CustomCover
from codex.settings import COMICBOX_CONFIG, COVER_WORKERS

_COVER_RATIO = 1.5372233400402415  # modal cover ratio
THUMBNAIL_WIDTH = 165
THUMBNAIL_HEIGHT = round(THUMBNAIL_WIDTH * _COVER_RATIO)
_THUMBNAIL_SIZE = (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)


def _save_cover_to_cache(cover_path_str: str, data: bytes) -> None:
    """
    Save cover thumb image to the disk cache.

    Top-level so it runs inside worker subprocesses without
    pickling ``self``. The atomic-replace dance (stage to a sibling
    ``*.{pid}.tmp`` then ``os.replace``) means readers only ever see
    the pre-existing state or the fully written new file. Per-pid
    tmp filename prevents cross-worker collisions even in
    fork-mode start methods where workers might share module-level
    state.

    Empty ``data`` is the zero-byte ``tried-and-failed`` sentinel —
    creates an empty file so the cover endpoint can distinguish
    "not yet tried" (no file) from "tried and failed" (empty file).
    """
    cover_path = Path(cover_path_str)
    cover_path.parent.mkdir(exist_ok=True, parents=True)
    if data:
        tmp_path = cover_path.with_name(f"{cover_path.name}.{os.getpid()}.tmp")
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


def _render_cover_thumb(args: tuple) -> tuple[int, str, str | None]:
    """
    Render one cover thumbnail and write it to disk.

    Picklable; runs inside a worker subprocess. Accepts a
    pre-resolved ``(pk, db_path, cover_path_str, custom)`` tuple —
    workers don't touch the Django ORM. Calls
    ``_save_cover_to_cache`` directly (workers own the disk write
    so the WEBP bytes never round-trip through the executor's
    pickle channel), and returns only ``(pk, cover_path_str,
    error_msg_or_None)`` — metadata for the parent's logging +
    status loop.

    On failure, writes the zero-byte ``tried-and-failed`` sentinel
    via ``_save_cover_to_cache(path, b"")`` so the cover endpoint's
    polling loop can distinguish a missing file (not yet tried)
    from an empty one (tried and failed).
    """
    pk, db_path, cover_path_str, custom = args
    try:
        if custom:
            with Path(db_path).open("rb") as f:
                image_data = f.read()
        else:
            with Comicbox(db_path, config=COMICBOX_CONFIG) as car:
                image_data = car.get_cover_page(pdf_format="pixmap")
        if not image_data:
            _save_cover_to_cache(cover_path_str, b"")
            return pk, cover_path_str, "empty cover"
        with BytesIO(image_data) as image_io, Image.open(image_io) as img:
            img.thumbnail(
                _THUMBNAIL_SIZE,
                Image.Resampling.LANCZOS,
                reducing_gap=3.0,
            )
            buf = BytesIO()
            img.save(buf, "WEBP", method=6)
        _save_cover_to_cache(cover_path_str, buf.getvalue())
    except Exception as exc:
        # Disk-write attempt for the failure marker — best-effort.
        # Swallowing here is intentional: the caller is already
        # logging ``repr(exc)`` for the original failure, and a
        # marker write that fails just means the next cover request
        # will retry rather than serving the sentinel.
        with contextlib.suppress(Exception):
            _save_cover_to_cache(cover_path_str, b"")
        return pk, cover_path_str, repr(exc)
    return pk, cover_path_str, None


class CoverCreateThread(QueuedThread, CoverPathMixin, ABC):
    """Create methods for covers."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the lazy-built worker pool slot."""
        super().__init__(*args, **kwargs)
        self._cover_pool: ProcessPoolExecutor | None = None

    def _get_cover_pool(self) -> ProcessPoolExecutor:
        """
        Lazy-build the cover-rendering ProcessPoolExecutor.

        Cold-start cost is ~1-2 s per subprocess (fork + import
        Django + PIL + comicbox), so amortize across the thread's
        lifetime: spawn on first use, keep alive until the thread
        stops. ``CODEX_COVER_WORKERS`` (env / TOML
        ``librarian.cover_workers``) caps the worker count.
        """
        if self._cover_pool is None:
            self._cover_pool = ProcessPoolExecutor(max_workers=COVER_WORKERS)
        return self._cover_pool

    @override
    def stop(self) -> None:
        """Stop the thread and shut down the worker pool."""
        if self._cover_pool is not None:
            # Don't wait for outstanding tasks; the thread is
            # shutting down and any in-flight cover work would just
            # be discarded by the consumer (re-rendered on next
            # request via the 202-poll path).
            self._cover_pool.shutdown(wait=False, cancel_futures=True)
            self._cover_pool = None
        super().stop()

    def _filter_pending_pks(self, pks: Collection[int], *, custom: bool) -> list[int]:
        """
        Return only pks whose cover file isn't already on disk.

        Lifts the per-iteration ``cover_path.exists()`` stat into a
        single up-front pass so the work loop only runs against pks
        that genuinely need work — saves dispatch overhead on
        repeated CoverCreateAllTask runs and gives the multiprocessing
        path a tight set of work items.
        """
        return [
            pk for pk in pks if not self.get_cover_path(pk, custom=custom).is_file()
        ]

    @staticmethod
    def _resolve_db_paths(pks: Collection[int], *, custom: bool) -> dict[int, str]:
        """
        Batch-fetch ``pk -> filesystem path`` for the work items.

        Replaces N serial ``model.objects.only("path").get(pk=pk)``
        SELECTs (one per cover) with a single ``filter(pk__in=pks)``.
        The resulting dict gets threaded into the per-cover work
        function, removing Django's ORM from the cover-creation hot
        loop entirely.
        """
        if not pks:
            return {}
        model = CustomCover if custom else Comic
        return dict(model.objects.filter(pk__in=pks).values_list("pk", "path"))

    def _build_cover_work_items(
        self,
        pks: Collection[int],
        db_paths: dict[int, str],
        *,
        custom: bool,
    ) -> list[tuple[int, str, str, bool]]:
        """
        Pair each pk with its db_path and target cover_path.

        Skips pks whose db_path went missing (importer race).
        """
        work: list[tuple[int, str, str, bool]] = []
        for pk in pks:
            db_path = db_paths.get(pk)
            if db_path is None:
                continue
            cover_path_str = str(self.get_cover_path(pk, custom=custom))
            work.append((pk, db_path, cover_path_str, custom))
        return work

    def _bulk_create_comic_covers(self, pks, *, custom: bool) -> int:
        """
        Create bulk comic covers.

        Image-decode + LANCZOS resize + WEBP encode is CPU-bound and
        embarrassingly parallel across cover targets. Submit each
        target to a ``ProcessPoolExecutor`` and consume the
        completion stream via ``as_completed``.

        Workers own the full pipeline including the disk write —
        no inline cover-bytes path exists anymore (the cover
        endpoint serves from the on-disk cache via the 202-poll
        retry loop landed in cover-cleanup PR #606). Skipping the
        bytes round-trip through the executor's pickle channel
        avoids ~50 KB of IPC per cover and parallelizes the disk
        writes alongside the image pipeline.

        Workers return only ``(pk, cover_path_str,
        error_msg_or_None)`` — metadata for the parent's logging
        + status loop. Failures still write the zero-byte
        ``tried-and-failed`` sentinel from inside the worker so
        the on-disk shape is identical regardless of outcome.
        """
        # Up-front filter: drop pks that already have a cover on
        # disk. The remaining set is what we actually need to work
        # on.
        pending_pks = self._filter_pending_pks(tuple(pks), custom=custom)
        num_comics = len(pending_pks)
        if not num_comics:
            return 0
        # Single batched ``pk -> path`` map covers the full set of
        # work items; no per-cover SELECT inside the loop.
        db_paths = self._resolve_db_paths(pending_pks, custom=custom)
        work_items = self._build_cover_work_items(pending_pks, db_paths, custom=custom)
        # Race-window adjustment: if some pks vanished between
        # _resolve_db_paths and now, skip them silently in the status.
        skipped = num_comics - len(work_items)
        status = CreateCoversStatus(0, len(work_items))
        try:
            start_time = time()
            self.log.debug(f"Creating {len(work_items)} comic covers...")
            self.status_controller.start(status)
            pool = self._get_cover_pool()
            futures = [pool.submit(_render_cover_thumb, w) for w in work_items]
            for future in as_completed(futures):
                pk, _cover_path_str, err = future.result()
                if err:
                    self.log.warning(
                        f"Could not create cover thumbnail for pk={pk}: {err}"
                    )
                status.increment_complete()
                self.status_controller.update(status)
            desc = "custom" if custom else "comic"
            count = status.complete
            level = "INFO" if count else "DEBUG"
            elapsed = naturaldelta(time() - start_time)
            extra = f" ({skipped} skipped)" if skipped else ""
            self.log.log(level, f"Created {count} {desc} covers in {elapsed}{extra}.")
        finally:
            self.status_controller.finish(status)
        return status.complete or 0

    def create_all_covers(self) -> None:
        """Create all covers for all libraries."""
        pks = CustomCover.objects.values_list("pk", flat=True)
        count = self._bulk_create_comic_covers(pks, custom=True)
        pks = Comic.objects.values_list("pk", flat=True)
        count += self._bulk_create_comic_covers(pks, custom=False)

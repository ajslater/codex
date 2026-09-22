"""
The nightly orphan sweep keeps the thumbs that still have a row.

``_cleanup_orphan_covers`` took the cover model, the cover root and a
log name as three arguments that had to agree, and then built its
db-side path set with a hardcoded ``custom=False``. On the custom pass
it walked ``CUSTOM_COVERS_ROOT`` and compared what it found against
paths under ``COVERS_ROOT``, so nothing ever matched and every custom
cover thumbnail was an orphan on every nightly run.
"""

from __future__ import annotations

import shutil
from threading import Lock
from typing import TYPE_CHECKING, Final, override
from unittest.mock import patch

from django.test import TestCase
from loguru import logger

from codex.librarian.covers.coverd import CoverThread
from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models import (
    Comic,
    CustomCover,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from tests.tmp_dirs import tmp_dir

if TYPE_CHECKING:
    from pathlib import Path

_TMP_DIR: Final = tmp_dir("codex.tests.cleanup_orphan_covers")
_LIBRARY_DIR: Final = _TMP_DIR / "library"
_COVERS_ROOT: Final = _TMP_DIR / "covers"
_CUSTOM_COVERS_ROOT: Final = _TMP_DIR / "custom-covers"
# Not a real WEBP — nothing in the sweep decodes it.
_THUMB_BYTES: Final = b"RIFF\x00\x00\x00\x00WEBPfake-cover-bytes"
#: A pk no row owns, in either namespace.
_ORPHAN_PK: Final = 424242


class CleanupOrphanCoversTestCase(TestCase):
    """A thumb is only swept when its row is really gone."""

    @override
    def setUp(self) -> None:
        """One comic and one custom cover, each with a thumb on disk."""
        for path in (_LIBRARY_DIR, _COVERS_ROOT, _CUSTOM_COVERS_ROOT):
            path.mkdir(exist_ok=True, parents=True)

        # The cover roots are class attributes resolved at import time from
        # ROOT_CACHE_PATH, so redirect them rather than the settings they came
        # from — otherwise this test would sweep the real cover cache.
        for attr, root in (
            ("COVERS_ROOT", _COVERS_ROOT),
            ("CUSTOM_COVERS_ROOT", _CUSTOM_COVERS_ROOT),
        ):
            patcher = patch.object(CoverPathMixin, attr, root)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.comic = self._make_comic()  # pyright: ignore[reportUninitializedInstanceVariable]
        cover_path = _LIBRARY_DIR / "cover.png"
        cover_path.write_bytes(b"not really a png")
        self.custom_cover = CustomCover.objects.create(path=str(cover_path))  # pyright: ignore[reportUninitializedInstanceVariable]

        self.comic_thumb = self._write_thumb(self.comic.pk, custom=False)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.custom_thumb = self._write_thumb(self.custom_cover.pk, custom=True)  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self) -> None:
        """Remove the temp library and cover roots."""
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    @staticmethod
    def _make_comic() -> Comic:
        """Create a Comic row backed by a touch file."""
        library = Library.objects.create(path=str(_LIBRARY_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        path = _LIBRARY_DIR / "comic.cbz"
        path.touch()
        return Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name="comic",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=1,
            file_type="CBZ",
        )

    @staticmethod
    def _write_thumb(pk: int, *, custom: bool) -> Path:
        """Write a thumb where the cover cache would hold it."""
        thumb_path = CoverPathMixin.get_cover_path(pk, custom=custom)
        thumb_path.parent.mkdir(exist_ok=True, parents=True)
        thumb_path.write_bytes(_THUMB_BYTES)
        return thumb_path

    @staticmethod
    def _cleanup() -> None:
        CoverThread(logger, LIBRARIAN_QUEUE, Lock()).cleanup_orphan_covers()

    def test_a_live_comic_thumb_is_kept(self) -> None:
        """Sanity: the comic pass always compared against the right root."""
        self._cleanup()

        assert self.comic_thumb.exists()

    def test_a_live_custom_cover_thumb_is_kept(self) -> None:
        """
        The regression: the custom pass condemned its whole root.

        Its db path set was built under ``COVERS_ROOT`` while the walk
        was over ``CUSTOM_COVERS_ROOT``, so no thumb on disk could ever
        match a row and the nightly job deleted all of them.
        """
        self._cleanup()

        assert self.custom_thumb.exists()

    def test_thumbs_with_no_row_are_swept(self) -> None:
        """The job still does its job, in both namespaces."""
        comic_orphan = self._write_thumb(_ORPHAN_PK, custom=False)
        custom_orphan = self._write_thumb(_ORPHAN_PK, custom=True)

        self._cleanup()

        assert not comic_orphan.exists()
        assert not custom_orphan.exists()

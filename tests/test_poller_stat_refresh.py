"""Integration test: poller refreshes stale Comic.stat without bumping updated_at."""

import os
import shutil
from pathlib import Path
from typing import override
from unittest.mock import MagicMock

from django.test import TestCase

from codex.librarian.fs.poller.poller import LibraryPollerThread
from codex.librarian.fs.poller.snapshot_diff import SnapshotDiff, StaleStatRefresh
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume

_TMP_DIR = Path("/tmp/codex.tests.poller_stat_refresh")  # noqa: S108
_STALE_STAT: tuple = (33188, 12345, 0, 0, 0, 0, 100, 0, 1.0, 0)


def _create_comic_with_stale_stat() -> Comic:
    """Create a Comic row whose stored stat lies about its inode."""
    _TMP_DIR.mkdir(exist_ok=True, parents=True)
    comic_path = _TMP_DIR / "stale.cbz"
    comic_path.touch()
    library = Library.objects.create(path=str(_TMP_DIR))
    publisher = Publisher.objects.create(name="P")
    imprint = Imprint.objects.create(name="I", publisher=publisher)
    series = Series.objects.create(name="S", imprint=imprint, publisher=publisher)
    volume = Volume.objects.create(
        name="2024", series=series, imprint=imprint, publisher=publisher
    )
    comic = Comic.objects.create(
        library=library,
        path=str(comic_path),
        issue_number=1,
        name="stale",
        publisher=publisher,
        imprint=imprint,
        series=series,
        volume=volume,
        size=100,
        year=2024,
        month=1,
        day=1,
    )
    # Bake a stale stat directly via UPDATE so the row's updated_at
    # snapshot we capture below is the post-create one, not a
    # post-stat-write one.
    Comic.objects.filter(pk=comic.pk).update(stat=list(_STALE_STAT))
    comic.refresh_from_db()
    return comic


def _new_poller_thread() -> LibraryPollerThread:
    """Build a poller without starting the threading machinery."""
    thread = LibraryPollerThread.__new__(LibraryPollerThread)
    thread.log = MagicMock()
    return thread


def _diff_with_refreshes(
    refreshes: tuple[StaleStatRefresh, ...],
) -> SnapshotDiff:
    diff = SnapshotDiff.__new__(SnapshotDiff)
    diff.stale_stat_refreshes = refreshes
    return diff


class StaleStatRefreshTestCase(TestCase):
    """``LibraryPollerThread._refresh_stale_stats`` writes stat without updated_at."""

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_stat_refresh_writes_stat_and_does_not_bump_updated_at(self) -> None:
        """Stat field is rewritten; updated_at and content fields stay put."""
        comic = _create_comic_with_stale_stat()
        original_updated_at = comic.updated_at

        # Simulate a Docker remount: same content, brand-new inode.
        fresh_inode = 99999
        fresh_stat = os.stat_result((33188, fresh_inode, 0, 0, 0, 0, 100, 0, 1.0, 0))
        diff = _diff_with_refreshes(
            (StaleStatRefresh(path=comic.path, model=Comic, disk_stat=fresh_stat),)
        )

        _new_poller_thread()._refresh_stale_stats(diff)  # noqa: SLF001

        comic.refresh_from_db()
        # The stored stat now reflects disk's fresh inode...
        assert comic.stat is not None
        assert comic.stat[1] == fresh_inode
        # ...but the row's updated_at didn't advance, so bookmark
        # "fresh" semantics aren't disturbed.
        assert comic.updated_at == original_updated_at

    def test_stat_refresh_noop_when_diff_empty(self) -> None:
        """An empty stale-stat list must not touch the DB at all."""
        comic = _create_comic_with_stale_stat()
        diff = _diff_with_refreshes(())

        _new_poller_thread()._refresh_stale_stats(diff)  # noqa: SLF001

        comic.refresh_from_db()
        assert comic.stat == list(_STALE_STAT)

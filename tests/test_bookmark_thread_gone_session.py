"""
A queued bookmark update whose session is gone is dropped, not retried.

A page turn queued just before login is flushed after the login deleted
the visitor's session: the insert fails its foreign key check at commit.
BookmarkThread logged the traceback and kept the key, so it retried, and
failed, on every flush, every three seconds, for the life of the process.
"""

import shutil
from threading import Lock
from typing import Final, override
from unittest.mock import MagicMock

from django.test import TransactionTestCase
from loguru import logger

from codex.librarian.bookmark.bookmarkd import BookmarkThread
from codex.librarian.bookmark.tasks import BookmarkUpdateTask
from codex.models import Bookmark, Comic, Imprint, Library, Publisher, Series, Volume
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

_TMP_DIR: Final = tmp_dir("codex.tests.bookmark_gone_session")
_FLUSHES: Final = 3


class BookmarkThreadGoneSessionTestCase(TransactionTestCase):
    """The FK failure evicts the key."""

    @override
    def setUp(self) -> None:
        init_admin_flags()
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        library = Library.objects.create(path=str(_TMP_DIR))
        publisher = Publisher.objects.create(name="P")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        path = _TMP_DIR / "c.cbz"
        path.touch()
        self.comic = Comic.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=library,
            path=path,
            issue_number=1,
            name="c",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=1,
            page_count=10,
        )

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_an_update_for_a_gone_session_is_dropped(self) -> None:
        thread = BookmarkThread(logger, MagicMock(), Lock())
        thread.aggregate_items(
            BookmarkUpdateTask(
                auth_filter={"session_id": "gone-at-login"},
                comic_pks=(self.comic.pk,),
                updates={"page": 3},
            )
        )

        for _ in range(_FLUSHES):
            thread.send_all_items()

        assert not thread.cache
        assert not Bookmark.objects.exists()

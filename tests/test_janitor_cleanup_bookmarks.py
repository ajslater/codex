"""
The nightly sweep removes bookmarks that belong to nobody.

A bookmark belongs to a user or to a session. One with neither is
invisible to every reader and returned by no query, so nothing but a
sweep will ever collect it.

The sweep existed but could not work: its filter also required
``comic`` to be NULL, and ``Bookmark.comic`` is a non-nullable foreign
key, so the query matched nothing for its whole life. These pin the
corrected filter, and — just as importantly — that it does not touch the
rows that *do* have an owner.
"""

import shutil
from multiprocessing import Event
from pathlib import Path
from threading import Lock
from typing import Final, override
from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.utils import timezone
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.models import (
    Bookmark,
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)

_LIBRARY_DIR: Final = Path("/tmp/codex.tests.janitor.bookmarks")  # noqa: S108
_LIBRARY_PATH: Final = str(_LIBRARY_DIR)
_SESSION_KEY: Final = "sessionkeyforthetest"


def _make_janitor() -> Janitor:
    return Janitor(logger, LIBRARIAN_QUEUE, Lock(), Event())


class CleanupOrphanBookmarksTests(TestCase):
    """Only the ownerless rows go."""

    @override
    def setUp(self) -> None:
        # ``Comic`` presave stats the file, so it has to exist.
        _LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        (_LIBRARY_DIR / "c.cbz").write_text("comic")
        self.addCleanup(shutil.rmtree, _LIBRARY_DIR, ignore_errors=True)
        library = Library.objects.create(path=_LIBRARY_PATH)
        publisher = Publisher.objects.create(name="P")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        self.comic = Comic.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=library,
            path=f"{_LIBRARY_PATH}/c.cbz",
            issue_number=1,
            name="c",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=1,
        )
        self.user = User.objects.create_user(username="reader", password="x")  # noqa: S106 # pyright: ignore[reportUninitializedInstanceVariable]
        self.session = Session.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            session_key=_SESSION_KEY,
            session_data="",
            expire_date=timezone.now() + timezone.timedelta(days=1),
        )

    def _seed(self) -> tuple[Bookmark, Bookmark, Bookmark]:
        """One user-owned row, one session-owned row, one orphan."""
        owned = Bookmark.objects.create(user=self.user, comic=self.comic, finished=True)
        anonymous = Bookmark.objects.create(
            session=self.session, comic=self.comic, page=3
        )
        orphan = Bookmark.objects.create(comic=self.comic, page=7)
        return owned, anonymous, orphan

    def test_only_the_ownerless_row_is_deleted(self) -> None:
        """The sweep must not reach a reader's own progress."""
        owned, anonymous, orphan = self._seed()

        _make_janitor().cleanup_orphan_bookmarks()

        assert Bookmark.objects.filter(pk=owned.pk).exists()
        assert Bookmark.objects.filter(pk=anonymous.pk).exists()
        assert not Bookmark.objects.filter(pk=orphan.pk).exists()

    def test_the_deleted_pks_are_named(self) -> None:
        """
        The filter matched nothing for its whole life.

        So the first real run on any install is also its first ever, and
        the count has to be attributable.
        """
        _owned, _anonymous, orphan = self._seed()
        janitor = _make_janitor()
        mock_log = MagicMock()
        janitor.log = mock_log

        janitor.cleanup_orphan_bookmarks()

        messages = [call.args[-1] for call in mock_log.info.call_args_list]
        messages += [call.args[-1] for call in mock_log.log.call_args_list if call.args]
        assert any(str(orphan.pk) in message for message in messages), messages

    def test_a_clean_database_is_a_no_op(self) -> None:
        """Nothing to collect, nothing touched."""
        owned = Bookmark.objects.create(user=self.user, comic=self.comic, finished=True)

        _make_janitor().cleanup_orphan_bookmarks()

        assert Bookmark.objects.filter(pk=owned.pk).exists()
        assert Bookmark.objects.count() == 1

    def test_a_deleted_comic_cannot_orphan_a_bookmark(self) -> None:
        """
        ``comic`` is not in the filter, and does not need to be.

        The FK cascades, so a deleted comic takes its bookmarks with it.
        Requiring ``comic`` to be NULL is what made the sweep dead.
        """
        owned = Bookmark.objects.create(user=self.user, comic=self.comic, finished=True)

        self.comic.delete()

        assert not Bookmark.objects.filter(pk=owned.pk).exists()

"""
One bookmark per owner per comic, now enforced by the database.

``unique_together = (user, session, comic)`` could not enforce it: both
owner columns are nullable and SQL treats NULLs in a unique index as
distinct, so a reader's row and a second copy of it were equally legal.
Two writers for the same comic — a queued page turn and a synchronous
mark-read — could each pass the writer's "does a row exist" pass and each
insert.

These pin the partial constraints, and the write path's behavior when it
loses that race: the row it meant to insert is already there, so it
updates that one instead of failing.
"""

from __future__ import annotations

import shutil
from datetime import timedelta
from pathlib import Path
from typing import Final, override

import pytest
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone as django_timezone

from codex.librarian.bookmark.update import BookmarkUpdateMixin
from codex.models import (
    Bookmark,
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)

_TMP_DIR: Final = Path("/tmp/codex.tests.bookmark_unique")  # noqa: S108
_SESSION_KEY: Final = "bookmarkuniquesessionkey"
_PAGE: Final = 3
_OTHER_PAGE: Final = 9
#: One row for each of two distinct owners.
_TWO_OWNERS: Final = 2


class _BookmarkTestBase(TestCase):
    """One comic, one user, one session."""

    @override
    def setUp(self) -> None:
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, _TMP_DIR, ignore_errors=True)
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
        self.user = User.objects.create_user(username="reader", password="x")  # noqa: S106 # pyright: ignore[reportUninitializedInstanceVariable]
        self.session = Session.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            session_key=_SESSION_KEY,
            session_data="",
            expire_date=django_timezone.now() + timedelta(days=1),
        )


class BookmarkUniqueConstraintTests(_BookmarkTestBase):
    """The database refuses the second row."""

    def test_a_user_cannot_have_two_bookmarks_for_one_comic(self) -> None:
        Bookmark.objects.create(user=self.user, comic=self.comic, page=1)

        with pytest.raises(IntegrityError), transaction.atomic():
            Bookmark.objects.create(user=self.user, comic=self.comic, page=2)

    def test_a_session_cannot_either(self) -> None:
        Bookmark.objects.create(session=self.session, comic=self.comic, page=1)

        with pytest.raises(IntegrityError), transaction.atomic():
            Bookmark.objects.create(session=self.session, comic=self.comic, page=2)

    def test_a_user_row_and_a_session_row_coexist(self) -> None:
        """Two different owners, two different bookmarks."""
        Bookmark.objects.create(user=self.user, comic=self.comic, page=1)
        Bookmark.objects.create(session=self.session, comic=self.comic, page=2)

        assert Bookmark.objects.filter(comic=self.comic).count() == _TWO_OWNERS

    def test_two_users_coexist(self) -> None:
        other = User.objects.create_user(username="other", password="x")  # noqa: S106
        Bookmark.objects.create(user=self.user, comic=self.comic, page=1)
        Bookmark.objects.create(user=other, comic=self.comic, page=2)

        assert Bookmark.objects.filter(comic=self.comic).count() == _TWO_OWNERS


class BookmarkCreateRaceTests(_BookmarkTestBase):
    """Losing the insert race updates the winner's row."""

    def _create_once(self, auth_filter: dict, updates: dict) -> int:
        return BookmarkUpdateMixin._create_bookmarks_once(  # noqa: SLF001
            auth_filter, (self.comic.pk,), updates, django_timezone.now()
        )

    def test_a_lost_race_updates_instead_of_raising(self) -> None:
        """
        The create pass ran because phase 1 found nothing.

        By the time it inserts, the other writer's row is there. Seeding
        the row first and then calling the create pass is that race with
        the timing removed.
        """
        Bookmark.objects.create(
            user=self.user, comic=self.comic, page=_OTHER_PAGE, finished=False
        )

        count = self._create_once({"user_id": self.user.pk}, {"page": _PAGE})

        assert count == 1
        bookmark = Bookmark.objects.get(user=self.user, comic=self.comic)
        assert bookmark.page == _PAGE

    def test_a_lost_session_race_updates_too(self) -> None:
        Bookmark.objects.create(
            session=self.session, comic=self.comic, page=_OTHER_PAGE
        )

        count = self._create_once({"session_id": _SESSION_KEY}, {"page": _PAGE})

        assert count == 1
        assert Bookmark.objects.filter(comic=self.comic).count() == 1
        assert Bookmark.objects.get(comic=self.comic).page == _PAGE

    def test_an_uncontended_create_still_creates(self) -> None:
        """The retry must not be the only path that works."""
        count = self._create_once({"user_id": self.user.pk}, {"page": _PAGE})

        assert count == 1
        assert Bookmark.objects.get(user=self.user, comic=self.comic).page == _PAGE

    def test_the_public_entry_point_survives_the_race(self) -> None:
        """
        ``update_bookmarks`` is what both writers actually call.

        The row it will collide with lands *after* its own "does one
        exist" pass, which is why that pass did not find it. Blinding
        phase 1 once puts the create pass in front of a row it never
        saw, with the timing taken out.
        """
        Bookmark.objects.create(user=self.user, comic=self.comic, page=_OTHER_PAGE)

        class _BlindOnce(BookmarkUpdateMixin):
            blinded = False

            @classmethod
            @override
            def _update_bookmarks(cls, *args, **kwargs) -> tuple[int, set[int]]:
                if not cls.blinded:
                    cls.blinded = True
                    return 0, set()
                return super()._update_bookmarks(*args, **kwargs)

        count = _BlindOnce.update_bookmarks(
            {"user_id": self.user.pk}, (self.comic.pk,), {"page": _PAGE}
        )

        assert _BlindOnce.blinded, "phase 1 was never blinded"
        assert count == 1
        assert Bookmark.objects.filter(comic=self.comic).count() == 1
        assert Bookmark.objects.get(comic=self.comic).page == _PAGE

"""
Tests for the 0054 ``dedupe_bookmarks`` data migration.

The partial unique constraints the migration adds cannot be applied to a
table that already violates them, so the same migration merges the
existing duplicates first. This exercises that merge against every shape
the old schema allowed: several rows for one user and comic, several for
one session and comic, the legitimate pair of a user row and a session
row, and rows owned by nobody at all.

Duplicates cannot be seeded once the constraints exist, so these drop
them for the duration of each test and put them back.
"""

from __future__ import annotations

import importlib
import shutil
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Final, override

from django.apps import apps
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone as django_timezone

from codex.models import (
    Bookmark,
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)

_MIGRATION = importlib.import_module("codex.migrations.0054_bookmark_partial_unique")
dedupe_bookmarks = _MIGRATION.dedupe_bookmarks

_TMP_DIR: Final = Path("/tmp/codex.tests.bookmark_dedupe")  # noqa: S108
_SESSION_KEY: Final = "bookmarkdedupesessionkey"
_OLD_PAGE: Final = 5
_MID_PAGE: Final = 7
_WINNER_PAGE: Final = 2
#: One row for each of two distinct owners.
_TWO_OWNERS: Final = 2


@contextmanager
def _without_bookmark_constraints():
    """Drop the partial unique indexes so duplicates can be seeded."""
    constraints = tuple(Bookmark._meta.constraints)
    with connection.schema_editor(atomic=False) as editor:
        for constraint in constraints:
            editor.remove_constraint(Bookmark, constraint)
    try:
        yield
    finally:
        with connection.schema_editor(atomic=False) as editor:
            for constraint in constraints:
                editor.add_constraint(Bookmark, constraint)


def _age(bookmark: Bookmark, minutes: int) -> None:
    """Backdate a row past ``auto_now``, which ``.update()`` does not touch."""
    when = django_timezone.now() - timedelta(minutes=minutes)
    Bookmark.objects.filter(pk=bookmark.pk).update(updated_at=when)


class BookmarkDedupeMigrationTests(TransactionTestCase):
    """Every group the constraints would reject is collapsed."""

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

        def _comic(name: str) -> Comic:
            path = _TMP_DIR / f"{name}.cbz"
            path.touch()
            return Comic.objects.create(
                library=library,
                path=path,
                issue_number=1,
                name=name,
                publisher=publisher,
                imprint=imprint,
                series=series,
                volume=volume,
                size=1,
                page_count=20,
            )

        self.comic = _comic("one")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.other_comic = _comic("two")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.user = User.objects.create_user(username="reader", password="x")  # noqa: S106 # pyright: ignore[reportUninitializedInstanceVariable]
        self.session = Session.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            session_key=_SESSION_KEY,
            session_data="",
            expire_date=django_timezone.now() + timedelta(days=1),
        )

    def test_the_newest_row_survives_with_the_groups_progress(self) -> None:
        """The survivor must not be a downgrade of what the reader had."""
        with _without_bookmark_constraints():
            oldest = Bookmark.objects.create(
                user=self.user, comic=self.comic, page=_OLD_PAGE, finished=True
            )
            middle = Bookmark.objects.create(
                user=self.user, comic=self.comic, page=_MID_PAGE
            )
            newest = Bookmark.objects.create(user=self.user, comic=self.comic)
            _age(oldest, minutes=30)
            _age(middle, minutes=15)

            dedupe_bookmarks(apps, None)

        survivors = list(Bookmark.objects.filter(comic=self.comic))
        assert len(survivors) == 1, survivors
        assert survivors[0].pk == newest.pk
        # Finished anywhere in the group is finished: an explicit
        # mark-read is not undone by a later page turn's row.
        assert survivors[0].finished is True
        # The winner had no page of its own, so it takes the furthest.
        assert survivors[0].page == _MID_PAGE

    def test_a_winner_with_a_page_keeps_it(self) -> None:
        """The newest row's own position is the reader's real position."""
        with _without_bookmark_constraints():
            loser = Bookmark.objects.create(
                user=self.user, comic=self.comic, page=_MID_PAGE
            )
            Bookmark.objects.create(user=self.user, comic=self.comic, page=_WINNER_PAGE)
            _age(loser, minutes=30)

            dedupe_bookmarks(apps, None)

        assert Bookmark.objects.get(comic=self.comic).page == _WINNER_PAGE

    def test_session_duplicates_are_merged_too(self) -> None:
        with _without_bookmark_constraints():
            older = Bookmark.objects.create(
                session=self.session, comic=self.comic, finished=True
            )
            newer = Bookmark.objects.create(
                session=self.session, comic=self.comic, page=_WINNER_PAGE
            )
            _age(older, minutes=30)

            dedupe_bookmarks(apps, None)

        survivor = Bookmark.objects.get(comic=self.comic)
        assert survivor.pk == newer.pk
        assert survivor.finished is True

    def test_a_user_row_and_a_session_row_are_both_kept(self) -> None:
        """Different owners are not duplicates."""
        with _without_bookmark_constraints():
            Bookmark.objects.create(user=self.user, comic=self.comic, page=1)
            Bookmark.objects.create(session=self.session, comic=self.comic, page=2)

            dedupe_bookmarks(apps, None)

        assert Bookmark.objects.filter(comic=self.comic).count() == _TWO_OWNERS

    def test_other_comics_are_not_touched(self) -> None:
        """The grouping is per comic, not per owner."""
        with _without_bookmark_constraints():
            Bookmark.objects.create(user=self.user, comic=self.comic, page=1)
            Bookmark.objects.create(user=self.user, comic=self.comic, page=2)
            elsewhere = Bookmark.objects.create(
                user=self.user, comic=self.other_comic, page=_MID_PAGE
            )

            dedupe_bookmarks(apps, None)

        assert Bookmark.objects.filter(pk=elsewhere.pk).exists()
        assert Bookmark.objects.filter(comic=self.comic).count() == 1

    def test_rows_owned_by_nobody_are_deleted(self) -> None:
        """
        They satisfy both constraints and are still garbage.

        No query in the app can reach a row with neither owner, so the
        table starts clean rather than carrying them forward.
        """
        with _without_bookmark_constraints():
            orphan = Bookmark.objects.create(comic=self.comic, page=1)
            kept = Bookmark.objects.create(user=self.user, comic=self.comic, page=2)

            dedupe_bookmarks(apps, None)

        assert not Bookmark.objects.filter(pk=orphan.pk).exists()
        assert Bookmark.objects.filter(pk=kept.pk).exists()

    def test_a_clean_table_is_a_no_op(self) -> None:
        kept = Bookmark.objects.create(user=self.user, comic=self.comic, page=1)

        dedupe_bookmarks(apps, None)

        assert Bookmark.objects.filter(pk=kept.pk, page=1).exists()
        assert Bookmark.objects.count() == 1

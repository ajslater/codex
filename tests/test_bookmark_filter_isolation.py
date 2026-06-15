"""
Per-user isolation for the bookmark read-state filters.

The browser read/unread/in-progress filter is built by
``BrowserFilterBookmarkView.get_bookmark_filter`` on top of
``BookmarkFilterMixin.get_my_bookmark_filter``. A
:class:`~codex.models.bookmark.Bookmark` row belongs to *either* a user *or* a
session (the other FK NULL), with at most one row per (user, session, comic).

Two regressions are locked in here:

* The UNREAD filter must mean "*I* have not finished it" — the negation of my
  own finished bookmark. A bare ``Q(bookmark=None)`` tested whether the comic
  had *any* bookmark from *any* user, so once an admin finished a comic it
  dropped out of every *other* user's unread view too.
* An anonymous visitor with no established session must not resolve to a raw
  ``session_id IS NULL`` predicate, which matches every authenticated user's
  bookmarks.
"""

import shutil
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import override

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.models import Session
from django.test import TestCase
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
from codex.views.browser.filters.bookmark import BrowserFilterBookmarkView

TMP_DIR = Path("/tmp/codex.tests.bookmark_isolation")  # noqa: S108


def _make_session(session_key: str) -> None:
    """Create a real django_session row so the Bookmark FK insert is valid."""
    Session.objects.create(
        session_key=session_key,
        session_data="",
        expire_date=django_timezone.now() + timedelta(days=1),
    )


def _build_view(*, user, session_key, choice):
    """
    Construct a bookmark-filter view without DRF's request lifecycle.

    ``__new__`` skips ``__init__`` (and the heavy view setup it triggers);
    we wire in only the three attributes ``get_bookmark_filter`` reads:
    the per-request bm-rel cache, a stubbed request, and the parsed params.
    """
    view = BrowserFilterBookmarkView.__new__(BrowserFilterBookmarkView)
    view.init_bookmark_filter()
    view.request = SimpleNamespace(  # pyright: ignore[reportAttributeAccessIssue]
        user=user,
        session=SimpleNamespace(session_key=session_key),
    )
    view.set_params({"filters": {"bookmark": choice}})
    return view


class BookmarkFilterIsolationTestCase(TestCase):
    """Exercise read-state isolation across users and sessions."""

    @override
    def setUp(self) -> None:
        """Seed two comics: one finished by admin, one untouched."""
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Kodansha")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        volume = Volume.objects.create(
            name="2024", series=series, imprint=imprint, publisher=publisher
        )

        def _comic(name: str) -> Comic:
            path = TMP_DIR / f"{name}.cbz"
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
                page_count=10,
            )

        # ``admin_read`` is finished by admin; ``untouched`` has no bookmark.
        self.admin_read = _comic("admin_read")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.untouched = _comic("untouched")  # pyright: ignore[reportUninitializedInstanceVariable]

        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin",
            password="x",  # noqa: S106
            is_staff=True,
        )
        self.aj = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="aj",
            password="x",  # noqa: S106
        )
        # Admin marks one comic read: user-scoped row, session_id NULL.
        Bookmark.objects.create(
            comic=self.admin_read, user=self.admin, session=None, finished=True
        )

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _pks(self, *, choice, user, session_key) -> set[int]:
        """Resolve the named bookmark filter to the set of matching comic pks."""
        view = _build_view(user=user, session_key=session_key, choice=choice)
        q = view.get_bookmark_filter(Comic)
        return set(Comic.objects.filter(q).values_list("pk", flat=True))

    # --- UNREAD: the reported bug ------------------------------------

    def test_unread_admin_excludes_own_read(self) -> None:
        """Admin's unread view hides the comic admin finished."""
        pks = self._pks(choice="UNREAD", user=self.admin, session_key=None)
        assert self.admin_read.pk not in pks
        assert self.untouched.pk in pks

    def test_unread_other_user_still_sees_admin_read(self) -> None:
        """User aj marked nothing read, so admin's read comic is unread to aj."""
        pks = self._pks(choice="UNREAD", user=self.aj, session_key=None)
        assert self.admin_read.pk in pks
        assert self.untouched.pk in pks

    def test_unread_anonymous_still_sees_admin_read(self) -> None:
        """An anonymous (no-session) visitor inherits no read state."""
        pks = self._pks(choice="UNREAD", user=AnonymousUser(), session_key=None)
        assert self.admin_read.pk in pks
        assert self.untouched.pk in pks

    # --- READ: per-user scoping --------------------------------------

    def test_read_admin_sees_own(self) -> None:
        """Admin's read view contains the comic admin finished."""
        pks = self._pks(choice="READ", user=self.admin, session_key=None)
        assert self.admin_read.pk in pks
        assert self.untouched.pk not in pks

    def test_read_other_user_sees_nothing(self) -> None:
        """User aj finished nothing, so aj's read view is empty."""
        pks = self._pks(choice="READ", user=self.aj, session_key=None)
        assert not pks

    def test_read_anonymous_sees_nothing(self) -> None:
        """An anonymous (no-session) visitor has no read comics."""
        pks = self._pks(choice="READ", user=AnonymousUser(), session_key=None)
        assert not pks

    # --- session-scoped anonymous bookmarks --------------------------

    def test_session_bookmarks_isolated(self) -> None:
        """A session-owned finished bookmark resolves for that session only."""
        _make_session("sess-abc")
        Bookmark.objects.create(
            comic=self.untouched, user=None, session_id="sess-abc", finished=True
        )
        # Owning session: READ contains it, UNREAD excludes it.
        read = self._pks(choice="READ", user=AnonymousUser(), session_key="sess-abc")
        assert self.untouched.pk in read
        unread = self._pks(
            choice="UNREAD", user=AnonymousUser(), session_key="sess-abc"
        )
        assert self.untouched.pk not in unread
        # A different session inherits nothing.
        other = self._pks(choice="READ", user=AnonymousUser(), session_key="sess-xyz")
        assert self.untouched.pk not in other

"""
Visibility of scanner-stamped (pending-delete) rows.

A row whose path a scan could not find carries ``missing_since`` and is
kept for a retention window instead of being deleted, so its bookmarks
survive a filesystem outage. It must be hidden from ordinary users for
that window and stay visible to staff, who are the only ones who can act
on it.

Nothing writes the stamp yet, which is what makes these tests possible in
isolation: every case hand-stamps a row with ``.update(missing_since=…)``
and asserts what moves.

Two deliberate asymmetries are pinned here rather than left to be
rediscovered:

* **Writes land, reads hide.** A bookmark PATCH resolves its target
  through the same filtered queryset the browser uses. Left hidden, the
  queryset is empty, ``update_bookmarks`` normalizes nothing, and the
  view returns a bare 200 with the write silently dropped -- the reader
  would be back where it started once the stamp cleared.
* **The reader keeps the book open.** Hiding a stamped comic from the
  reader raises ``NotFound`` carrying a ``route`` that nothing consumes,
  so the user gets a dead-end panel with a retry button that fails for
  the whole window.
"""

import json
import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import AnonymousUser, User
from django.db.models import Q
from django.test import Client, TestCase
from django.utils import timezone

from codex.models import (
    Bookmark,
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.models.comic import ComicFTS
from codex.startup import init_admin_flags
from codex.views.auth import MissingACLFilterMixin
from codex.views.reader._archive_cache import page_acl_cache

TMP_DIR = Path("/tmp/codex.tests.missing_acl")  # noqa: S108
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


def _stamp(model, pk) -> None:
    """Hand-stamp a row the way the scanner will."""
    model.objects.filter(pk=pk).update(missing_since=timezone.now())
    # The page endpoint memoizes (auth_key, comic_pk) -> (path, type) for
    # 60s with no invalidation hook, so a stamp is invisible to it until
    # the entry ages out. Tests would flake without this.
    page_acl_cache.clear()


class MissingACLFilterTestCase(TestCase):
    """The seam itself, without a request."""

    def test_staff_see_everything(self) -> None:
        """An admin is the one person who can act on a stamped row."""
        user = User(username="admin", is_staff=True)
        assert MissingACLFilterMixin.get_missing_acl_filter(Comic, user) == Q()

    def test_anonymous_is_not_staff(self) -> None:
        """
        AnonymousUser defines ``is_staff = False`` as a class attribute.

        So a plain attribute read is correct and a defensive
        ``getattr(user, "is_staff", False)`` would only mislead the next
        reader -- its default can never be exercised.
        """
        q = MissingACLFilterMixin.get_missing_acl_filter(Comic, AnonymousUser())
        assert q == Q(missing_since__isnull=True)

    def test_collections_reach_the_column_through_comic(self) -> None:
        """Only Comic and Folder own the column; the rest traverse to it."""
        user = User(username="plain")
        for model in (Publisher, Imprint, Series, Volume):
            q = MissingACLFilterMixin.get_missing_acl_filter(model, user)
            assert q == Q(comic__missing_since__isnull=True), model.__name__

    def test_folder_needs_both_clauses(self) -> None:
        """
        Folder is the exception and the easiest clause to omit.

        ``get_rel_prefix(Folder)`` is the ancestor-inclusive ``comic__``
        m2m, which answers "has a live descendant comic". A Folder also
        carries its OWN stamp from dirs_deleted, so the self clause is
        needed too -- the same asymmetry ``_library_rel`` encodes.
        """
        q = MissingACLFilterMixin.get_missing_acl_filter(Folder, User(username="u"))
        assert q == Q(comic__missing_since__isnull=True) & Q(missing_since__isnull=True)


class MissingVisibilityTestCase(TestCase):
    """End-to-end: what a stamped row does to each surface."""

    @override
    def setUp(self) -> None:
        """One publisher, one series, three comics, one folder."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=str(TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Ser", imprint=imprint, publisher=publisher
        )
        volume = Volume.objects.create(
            name="2024", series=self.series, imprint=imprint, publisher=publisher
        )
        self.folder = Folder.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=self.library, path=str(TMP_DIR), name=TMP_DIR.name
        )
        self.comics: list[Comic] = []  # pyright: ignore[reportUninitializedInstanceVariable]
        for n in (1, 2, 3):
            path = TMP_DIR / f"c{n}.cbz"
            path.touch()
            comic = Comic.objects.create(
                library=self.library,
                path=path,
                issue_number=n,
                name=f"C{n}",
                publisher=publisher,
                imprint=imprint,
                series=self.series,
                volume=volume,
                parent_folder=self.folder,
                size=42,
            )
            comic.folders.add(self.folder)
            self.comics.append(comic)

        self.plain = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="plain", password=_TEST_PASSWORD
        )
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(self.plain)

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        page_acl_cache.clear()
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _browse(self, collection: str, pks: str = "", page: int = 1):
        suffix = f"/{pks}/{page}" if pks else ""
        response = self.client.get(
            f"/api/v4/browse/{collection}{suffix}",
            {"filters": json.dumps({}), "search": ""},
        )
        if response.status_code in (302, 303):
            response = self.client.get(response.headers["Location"])
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)

    def test_a_stamped_comic_leaves_the_listing(self) -> None:
        """The headline behaviour."""
        assert self._browse("comics")["count"] == len(self.comics)
        _stamp(Comic, self.comics[0].pk)
        assert self._browse("comics")["count"] == len(self.comics) - 1

    def test_a_stamped_comic_stays_visible_to_staff(self) -> None:
        """An admin can still see what the feature is holding."""
        _stamp(Comic, self.comics[0].pk)
        self.client.force_login(self.admin)
        assert self._browse("comics")["count"] == len(self.comics)

    def test_the_row_survives(self) -> None:
        """Hidden is not deleted -- that is the entire point."""
        _stamp(Comic, self.comics[0].pk)
        assert Comic.objects.filter(pk=self.comics[0].pk).exists()

    def test_a_bookmark_survives_the_stamp(self) -> None:
        """The read progress the feature exists to protect."""
        Bookmark.objects.create(user=self.plain, comic=self.comics[0], page=140)
        _stamp(Comic, self.comics[0].pk)
        bookmark = Bookmark.objects.get(user=self.plain, comic=self.comics[0])
        assert bookmark.page == 140  # noqa: PLR2004

    def test_a_container_narrows_in_lockstep(self) -> None:
        """
        child_count, the order aggregates and the display query agree.

        The collection models reach Comic through a hard AND that keeps
        the join INNER, so a container whose every comic is stamped is
        eliminated from the count query and the display query alike.
        """
        rows = self._browse("folders")["collections"]
        assert rows[0]["childCount"] == len(self.comics)
        _stamp(Comic, self.comics[0].pk)
        rows = self._browse("folders")["collections"]
        assert rows[0]["childCount"] == len(self.comics) - 1

    def test_a_container_whose_comics_are_all_stamped_disappears(self) -> None:
        """The INNER join plus the WHERE eliminates it; no count divergence."""
        assert self._browse("folders")["count"] == 1
        for comic in self.comics:
            _stamp(Comic, comic.pk)
        assert self._browse("folders")["count"] == 0

    def test_a_stamped_folder_with_live_comics_is_hidden(self) -> None:
        """
        The Folder self-clause.

        Its comics are all live, so the ancestor-inclusive ``comic__``
        clause passes. Only the self clause hides it.
        """
        assert self._browse("folders")["count"] == 1
        _stamp(Folder, self.folder.pk)
        assert self._browse("folders")["count"] == 0

    def _search(self, text: str) -> int:
        response = self.client.get(
            "/api/v4/browse/comics",
            {"filters": json.dumps({}), "search": text},
        )
        if response.status_code in (302, 303):
            response = self.client.get(response.headers["Location"])
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)["count"]

    def test_search_hides_a_stamped_comic(self) -> None:
        """
        The Comic-level predicate reaches the FTS traversal.

        ``get_fts_filter`` builds a relation traversal inside the
        caller's own queryset and ANDs it into the same Q as the ACL, so
        there is no "FTS first, then filter" stage that could bypass the
        seam -- and the FTS row is deliberately NOT removed on stamping,
        which would fight ``remove_stale_records`` and thrash FTS5 for
        the whole window.

        The FTS table is populated by the librarian's index sync, so
        this seeds the rows directly.
        """
        for comic in self.comics:
            ComicFTS.objects.create(comic=comic, name=comic.name)
        assert self._search("C1") == 1
        _stamp(Comic, self.comics[0].pk)
        assert self._search("C1") == 0

    def test_a_bookmark_write_still_lands_on_a_stamped_comic(self) -> None:
        """
        D7: writes land, reads hide.

        A user is on page 140 when the mount blips and reads to the end.
        Without ``include_missing`` every position write returns 200 and
        goes nowhere, and a day later they are back on page 140 -- worse
        than today's loud deletion, and the exact outcome the feature
        exists to prevent.
        """
        comic = self.comics[0]
        _stamp(Comic, comic.pk)
        response = self.client.patch(
            f"/api/v4/browse/comics/{comic.pk}/bookmark",
            data=json.dumps({"page": 140}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        bookmark = Bookmark.objects.filter(user=self.plain, comic=comic).first()
        assert bookmark is not None, "the write was silently dropped"
        assert bookmark.page == 140  # noqa: PLR2004

    def test_the_reader_still_opens_a_stamped_comic(self) -> None:
        """
        D8: an open book is not yanked mid-read.

        The reader degrades on its own when a page is really unreadable,
        via the page endpoint's existing FileNotFoundError arm.
        """
        comic = self.comics[0]
        _stamp(Comic, comic.pk)
        response = self.client.get(f"/api/v4/reader/comics/{comic.pk}")
        assert response.status_code == _HTTP_OK, response.content
        # ``books`` is keyed by position -- current/prev/next -- so the
        # stamped comic being ``current`` is the assertion that matters.
        books = _v4(response)["books"]
        assert books["current"]["pk"] == comic.pk, books


class MissingCoverRouteTestCase(TestCase):
    """The cover route composes the ACL halves by hand."""

    @override
    def setUp(self) -> None:
        """One series with two comics."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Ser", imprint=imprint, publisher=publisher
        )
        volume = Volume.objects.create(
            name="2024", series=self.series, imprint=imprint, publisher=publisher
        )
        self.comics: list[Comic] = []  # pyright: ignore[reportUninitializedInstanceVariable]
        for n in (1, 2):
            path = TMP_DIR / f"cover{n}.cbz"
            path.touch()
            self.comics.append(
                Comic.objects.create(
                    library=library,
                    path=path,
                    issue_number=n,
                    name=f"Cover{n}",
                    sort_name=f"Cover{n}",
                    publisher=publisher,
                    imprint=imprint,
                    series=self.series,
                    volume=volume,
                    size=42,
                )
            )
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="plain", password=_TEST_PASSWORD
        )

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def test_a_stamped_comic_is_not_picked_as_a_collection_cover(self) -> None:
        """
        The cover route the web client actually calls.

        ``_resolve_collection_comic_pk`` is a module-level function that
        composes the two classmethod ACL halves by hand instead of going
        through an instance's ``get_acl_filter``, so the seam does not
        reach it. Left alone, a healthy series card renders the cover of
        a comic that is gone.
        """
        from codex.views.browser.cover import (
            _resolve_collection_comic_pk,
        )

        picked = _resolve_collection_comic_pk("series", self.series.pk, self.user)
        assert picked == self.comics[0].pk

        _stamp(Comic, self.comics[0].pk)
        picked = _resolve_collection_comic_pk("series", self.series.pk, self.user)
        assert picked == self.comics[1].pk

"""
Multi-user semantics of the UNREAD bookmark filter.

The old filter was ``Q(bookmark=None) | (mine & unfinished)``:
``bookmark=None`` matches only comics with no bookmark from ANY user or
session, so a comic finished by someone else matched neither arm and
silently vanished from my unread listing. The fix probes "I have no
finished bookmark on this comic" with a correlated NOT EXISTS, scoped
to the requesting user/session and bound to the same joined comic row
as the other filters.
"""

import json
import re
import shutil
from typing import Final, override

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from codex.models import (
    Bookmark,
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

TMP_DIR = tmp_dir("codex.tests.browser_bookmark_unread")
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


def _exists_subqueries(sql: str) -> list[str]:
    """Each ``EXISTS(...)`` body, matched to its closing paren."""
    blocks = []
    for match in re.finditer(r"EXISTS\(", sql):
        depth = 1
        for i in range(match.end(), len(sql)):
            depth += {"(": 1, ")": -1}.get(sql[i], 0)
            if not depth:
                blocks.append(sql[match.end() : i])
                break
    return blocks


class BookmarkUnreadFilterTestCase(TestCase):
    """UNREAD must key on MY bookmarks only and bind per comic row."""

    @override
    def setUp(self) -> None:
        """Two publishers; pub1 has a 2020 and a 2021 comic."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        self.comics: list[Comic] = []  # pyright: ignore[reportUninitializedInstanceVariable]
        self.pubs: list[Publisher] = []  # pyright: ignore[reportUninitializedInstanceVariable]
        spec = (("Pub1", ((1, 2020), (2, 2021))), ("Pub2", ((3, 2021),)))
        for pub_name, issues in spec:
            publisher = Publisher.objects.create(name=pub_name)
            self.pubs.append(publisher)
            imprint = Imprint.objects.create(name=f"Imp{pub_name}", publisher=publisher)
            series = Series.objects.create(
                name=f"Ser{pub_name}", imprint=imprint, publisher=publisher
            )
            volume = Volume.objects.create(
                name="2024", series=series, imprint=imprint, publisher=publisher
            )
            for n, year in issues:
                path = TMP_DIR / f"c{n}.cbz"
                path.touch()
                self.comics.append(
                    Comic.objects.create(
                        library=library,
                        path=path,
                        issue_number=n,
                        name=f"C{n}",
                        year=year,
                        publisher=publisher,
                        imprint=imprint,
                        series=series,
                        volume=volume,
                        size=42,
                    )
                )

        self.me = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="me", password=_TEST_PASSWORD, is_staff=True
        )
        self.other = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="other", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.me)

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _browse(self, collection: str, filters: dict):
        params = {"filters": json.dumps(filters), "search": ""}
        response = self.client.get(f"/api/v4/browse/{collection}", params)
        if response.status_code in (302, 303):
            response = self.client.get(response.headers["Location"])
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)

    def _unread_comic_count(self) -> int:
        return self._browse("comics", {"bookmark": "UNREAD"})["count"]

    def test_foreign_finished_bookmark_does_not_hide_comic(self) -> None:
        """A comic finished only by another user stays in MY unread list."""
        assert self._unread_comic_count() == len(self.comics)
        Bookmark.objects.create(user=self.other, comic=self.comics[0], finished=True)
        # Pre-fix: Q(bookmark=None) failed (a bookmark exists) and the
        # mine-unfinished arm failed (it isn't mine) — the comic vanished.
        assert self._unread_comic_count() == len(self.comics)

    def test_my_finished_bookmark_hides_comic(self) -> None:
        """A comic I finished leaves my unread list (and counts as READ)."""
        Bookmark.objects.create(user=self.me, comic=self.comics[0], finished=True)
        assert self._unread_comic_count() == len(self.comics) - 1
        read = self._browse("comics", {"bookmark": "READ"})["count"]
        assert read == 1, read

    def test_collection_rows_follow_my_bookmarks_only(self) -> None:
        """A collection drops from UNREAD only when I finished all its comics."""
        pub2_comic = self.comics[2]
        # Someone else finishing Pub2's only comic must not hide Pub2 from me.
        Bookmark.objects.create(user=self.other, comic=pub2_comic, finished=True)
        data = self._browse("publishers", {"bookmark": "UNREAD"})
        names = {c["name"] for c in data["collections"]}
        assert "Pub2" in names or not data["collections"], data
        # Me finishing it must.
        Bookmark.objects.create(user=self.me, comic=pub2_comic, finished=True)
        data = self._browse("publishers", {"bookmark": "UNREAD"})
        names = {c["name"] for c in data["collections"]}
        assert "Pub2" not in names, names

    def test_unread_binds_to_the_same_comic_row_as_field_filters(self) -> None:
        """
        Combined field filter + UNREAD must match on ONE comic, not two.

        Pub1 has a 2020 comic (which I finished) and a 2021 comic
        (unread). Filtering year=2020 + UNREAD: no single Pub1 comic is
        both from 2020 and unread by me, so Pub1 must not appear. An
        uncorrelated exists would wrongly keep it (one comic matches the
        year, a different one is unread).
        """
        Bookmark.objects.create(user=self.me, comic=self.comics[0], finished=True)
        data = self._browse("publishers", {"bookmark": "UNREAD", "year": [2020]})
        names = {c["name"] for c in data["collections"]}
        assert "Pub1" not in names, names
        # Sanity: dropping the year filter brings Pub1 back via its 2021 comic.
        data = self._browse("publishers", {"bookmark": "UNREAD"})
        names = {c["name"] for c in data["collections"]}
        assert "Pub1" in names, names

    def test_my_unfinished_bookmark_survives_a_foreign_finished_bookmark(
        self,
    ) -> None:
        """I'm on page 5 of C1 and another user finished it: still unread to me."""
        c1 = self.comics[0]
        Bookmark.objects.create(user=self.me, comic=c1, page=5)
        Bookmark.objects.create(user=self.other, comic=c1, page=10, finished=True)
        assert self._unread_comic_count() == len(self.comics)
        in_progress = self._browse("comics", {"bookmark": "IN_PROGRESS"})
        assert [book["ids"] for book in in_progress["books"]] == [[c1.pk]], in_progress

    def test_my_page_zero_bookmark_survives_a_foreign_finished_bookmark(
        self,
    ) -> None:
        """An opened-but-page-0 bookmark of mine must not change the answer."""
        c1 = self.comics[0]
        Bookmark.objects.create(user=self.me, comic=c1, page=0)
        Bookmark.objects.create(user=self.other, comic=c1, page=10, finished=True)
        assert self._unread_comic_count() == len(self.comics)

    def test_unread_sql_has_a_single_identity_scoped_not_exists(self) -> None:
        """The finished probe carries my identity in the same subquery."""
        Bookmark.objects.create(user=self.me, comic=self.comics[0], page=5)
        with CaptureQueriesContext(connection) as ctx:
            self._unread_comic_count()
        blocks = [
            block
            for query in ctx.captured_queries
            for block in _exists_subqueries(query["sql"])
            if "codex_bookmark" in block and "finished" in block
        ]
        assert blocks, [q["sql"] for q in ctx.captured_queries]
        for block in blocks:
            assert "user_id" in block or "session_id" in block, block

    def test_collection_cover_is_my_in_progress_comic(self) -> None:
        """
        The cover subquery nests the correlated probe; it must bind per comic.

        Pub1's only comic unread by me is C1, which another user finished.
        """
        c1, c2 = self.comics[0], self.comics[1]
        Bookmark.objects.create(user=self.me, comic=c1, page=5)
        Bookmark.objects.create(user=self.other, comic=c1, page=10, finished=True)
        Bookmark.objects.create(user=self.me, comic=c2, finished=True)
        data = self._browse("publishers", {"bookmark": "UNREAD"})
        pub1 = next(c for c in data["collections"] if c["name"] == "Pub1")
        assert pub1["coverPk"] == c1.pk, pub1

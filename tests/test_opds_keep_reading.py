"""
OPDS "Keep Reading" lists issues in progress, and each has a position.

Keep Reading used to be the UNREAD filter ordered by last-read time, so
its five-slot preview was padded with issues the reader had never
opened, and every one of those answered "no position" on the
Progression endpoint. It is now the IN_PROGRESS filter: every entry has
a bookmark row for the requesting identity. The unread groups still
list never-opened issues; their position is the empty 200.
"""

import json
import shutil
import xml.etree.ElementTree as ET
from datetime import timedelta
from typing import Final, override
from urllib.parse import unquote

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from codex.models import Bookmark, Comic, Imprint, Library, Publisher, Series, Volume
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_TMP_DIR: Final = tmp_dir("codex.tests.keep_reading")
_V2_START: Final = "/opds/v2.0/"
_V1_START: Final = "/opds/v1.2/"
_PROGRESSION_REL: Final = "http://opds-spec.org/progression"
_ATOM_NS: Final = "{http://www.w3.org/2005/Atom}"
_HTTP_OK: Final = 200
_N_COMICS: Final = 8
_PREVIEW_LIMIT: Final = 5
_PAGE_COUNT: Final = 11
_KEEP_READING: Final = "Keep Reading"
_KEEP_READING_SUBTITLE: Final = "Issues you have started, most recently read first."
_LATEST_UNREAD: Final = "Latest Unread"
_OLDEST_UNREAD: Final = "Oldest Unread"


def _group(feed: dict, title: str) -> dict | None:
    for group in feed.get("groups", []):
        if group.get("metadata", {}).get("title") == title:
            return group
    return None


def _pks(group: dict) -> list[int]:
    """Comic pks in feed order, read off each publication's progression link."""
    return [
        int(link["href"].rstrip("/").split("/")[-2])
        for pub in group.get("publications", [])
        for link in pub.get("links", [])
        if link.get("rel") == _PROGRESSION_REL
    ]


class KeepReadingSeedTestCase(TestCase):
    """Eight comics in one series, a reader, and another user."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        library = Library.objects.create(path=str(_TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        volume = Volume.objects.create(
            name="1", series=series, imprint=imprint, publisher=publisher
        )
        self.comics = []  # pyright: ignore[reportUninitializedInstanceVariable]
        for i in range(1, _N_COMICS + 1):
            path = _TMP_DIR / f"c{i}.cbz"
            path.touch()
            self.comics.append(
                Comic.objects.create(
                    library=library,
                    path=path,
                    issue_number=i,
                    name=f"c{i}",
                    publisher=publisher,
                    imprint=imprint,
                    series=series,
                    volume=volume,
                    file_type="CBZ",
                    page_count=_PAGE_COUNT,
                    size=1,
                )
            )
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="kr", password=_TEST_PASSWORD
        )
        self.other = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="other", password=_TEST_PASSWORD
        )
        self.client = Client()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    @staticmethod
    def _bookmark(user, comic, page, *, finished=False, age_s=0) -> None:
        bookmark = Bookmark.objects.create(
            user=user, comic=comic, page=page, finished=finished
        )
        Bookmark.objects.filter(pk=bookmark.pk).update(
            updated_at=timezone.now() - timedelta(seconds=age_s)
        )

    def _seed_reading(self) -> None:
        """c3 page 5 newest, c1 page 2, c5 page 0, c2 finished, other on c7."""
        c = self.comics
        self._bookmark(self.user, c[2], 5, age_s=10)
        self._bookmark(self.user, c[0], 2, age_s=20)
        self._bookmark(self.user, c[4], 0, age_s=30)
        self._bookmark(self.user, c[1], _PAGE_COUNT - 1, finished=True, age_s=5)
        self._bookmark(self.other, c[6], 4, age_s=1)

    def _feed(self, client: Client, url: str = _V2_START) -> dict:
        # Feeds are cached per identity; seeding happens between GETs.
        cache.clear()
        response = client.get(url)
        assert response.status_code == _HTTP_OK, response.content[:300]
        return json.loads(response.content)

    @staticmethod
    def _position(client: Client, pk: int):
        return client.get(f"/opds/v2.0/comics/{pk}/position")


class OPDSKeepReadingTestCase(KeepReadingSeedTestCase):
    """The group definition and its correspondence with the position endpoint."""

    def test_keep_reading_lists_only_my_started_unfinished_comics_most_recent_first(
        self,
    ) -> None:
        self._seed_reading()
        self.client.force_login(self.user)
        group = _group(self._feed(self.client), _KEEP_READING)
        assert group
        c = self.comics
        assert _pks(group) == [c[2].pk, c[0].pk]
        self_href = unquote(
            next(link["href"] for link in group["links"] if link["rel"] == "self")
        )
        assert "IN_PROGRESS" in self_href, self_href
        assert "orderBy=bookmark_updated_at" in self_href, self_href
        assert group["metadata"]["subtitle"] == _KEEP_READING_SUBTITLE
        assert group["metadata"]["numberOfItems"] == len(_pks(group))

    def test_every_keep_reading_entry_has_a_position(self) -> None:
        self._seed_reading()
        self.client.force_login(self.user)
        group = _group(self._feed(self.client), _KEEP_READING)
        assert group
        expected = {self.comics[2].pk: 0.5, self.comics[0].pk: 0.2}
        for pk in _pks(group):
            response = self._position(self.client, pk)
            assert response.status_code == _HTTP_OK
            assert response.json()["progression"] == expected[pk]

    def test_keep_reading_is_absent_when_nothing_is_in_progress(self) -> None:
        self._seed_reading()
        fresh = User.objects.create_user(username="fresh", password=_TEST_PASSWORD)
        logged_in = Client()
        logged_in.force_login(fresh)
        for client in (logged_in, Client()):
            feed = self._feed(client)
            assert _group(feed, _KEEP_READING) is None
            for title in (_LATEST_UNREAD, _OLDEST_UNREAD):
                group = _group(feed, title)
                assert group
                assert len(group["publications"]) == _PREVIEW_LIMIT

    def test_unread_groups_still_list_never_opened_comics_and_their_position_is_empty(
        self,
    ) -> None:
        self._seed_reading()
        self.client.force_login(self.user)
        group = _group(self._feed(self.client), _LATEST_UNREAD)
        assert group
        bookmarked = set(
            Bookmark.objects.filter(user=self.user).values_list("comic_id", flat=True)
        )
        never_opened = [pk for pk in _pks(group) if pk not in bookmarked]
        assert never_opened
        for pk in never_opened:
            response = self._position(self.client, pk)
            assert response.status_code == _HTTP_OK
            assert response.content == b""

    def test_preview_groups_omit_a_count_capped_at_the_preview_limit(self) -> None:
        """
        The browser counts previews only up to the limit.

        Seven unread comics would read as five, so a full preview carries
        no ``numberOfItems`` rather than a wrong one (it used to carry the
        parent view's count, which is 0 on the start page).
        """
        self._seed_reading()
        self.client.force_login(self.user)
        feed = self._feed(self.client)
        for title in (_LATEST_UNREAD, _OLDEST_UNREAD):
            group = _group(feed, title)
            assert group
            assert len(group["publications"]) == _PREVIEW_LIMIT
            assert "numberOfItems" not in group["metadata"]
            assert group["metadata"]["subtitle"]

    def test_opds_v1_keep_reading_uses_in_progress(self) -> None:
        self.client.force_login(self.user)
        cache.clear()
        response = self.client.get(_V1_START)
        assert response.status_code == _HTTP_OK
        root = ET.fromstring(response.content)  # noqa: S314
        entry = next(
            e
            for e in root.iter(f"{_ATOM_NS}entry")
            if (e.findtext(f"{_ATOM_NS}title") or "").endswith(_KEEP_READING)
        )
        hrefs = [
            unquote(link.get("href", "")) for link in entry.iter(f"{_ATOM_NS}link")
        ]
        assert any("IN_PROGRESS" in href for href in hrefs), hrefs

    def test_keep_reading_keeps_my_in_progress_comic_another_user_finished(
        self,
    ) -> None:
        c1 = self.comics[0]
        self._bookmark(self.user, c1, 5)
        self._bookmark(self.other, c1, _PAGE_COUNT - 1, finished=True)
        self.client.force_login(self.user)
        feed = self._feed(self.client)
        group = _group(feed, _KEEP_READING)
        assert group
        assert _pks(group) == [c1.pk]
        oldest = _group(feed, _OLDEST_UNREAD)
        assert oldest
        assert c1.pk in _pks(oldest)

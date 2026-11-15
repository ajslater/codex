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
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Final, override
from urllib.parse import parse_qs, unquote, urlsplit

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from codex.models import Bookmark, Comic, Imprint, Library, Publisher, Series, Volume
from codex.models.favorite import Favorite
from codex.startup import init_admin_flags
from codex.views.opds.v1.const import RootTopLinks
from codex.views.opds.v2.const import FAVORITES_PREVIEW_GROUP, PREVIEW_GROUPS
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
_FAVORITES: Final = "Favorites"
_ACQUISITION_REL: Final = "http://opds-spec.org/acquisition"
_DOWNLOAD_PK_RE: Final = re.compile(r"/c/(\d+)/download/")


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


def _v1_entry_href(feed: bytes, title: str) -> str | None:
    """Return the href of the v1 entry whose title ends with ``title``."""
    root = ET.fromstring(feed)  # noqa: S314
    for entry in root.iter(f"{_ATOM_NS}entry"):
        if (entry.findtext(f"{_ATOM_NS}title") or "").endswith(title):
            link = entry.find(f"{_ATOM_NS}link")
            assert link is not None
            return link.get("href", "")
    return None


def _v1_comic_pks(feed: bytes) -> list[int]:
    """Comic pks in v1 feed order, read off each entry's download link."""
    root = ET.fromstring(feed)  # noqa: S314
    return [
        int(match.group(1))
        for link in root.iter(f"{_ATOM_NS}link")
        if link.get("rel") == _ACQUISITION_REL
        and (match := _DOWNLOAD_PK_RE.search(link.get("href", "")))
    ]


def _sort_params(query_params) -> tuple:
    """Decode filters, orderBy and orderReverse from link query params."""
    filters = query_params.get("filters")
    if isinstance(filters, str):
        filters = json.loads(filters)
    return (
        dict(filters or {}),
        query_params.get("orderBy"),
        str(query_params.get("orderReverse")).lower(),
    )


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


class OPDSV1StartLinksTestCase(KeepReadingSeedTestCase):
    """The v1 start page entries: filters, order and Favorites."""

    def _v1(self, client: Client, url: str = _V1_START) -> bytes:
        # Feeds are cached per identity; seeding happens between GETs.
        cache.clear()
        response = client.get(url)
        assert response.status_code == _HTTP_OK, response.content[:300]
        return response.content

    def _v1_href(self, client: Client, title: str) -> str:
        href = _v1_entry_href(self._v1(client), title)
        assert href, title
        return href

    def test_latest_unread_href_carries_unread_filter_and_order(self) -> None:
        self.client.force_login(self.user)
        href = self._v1_href(self.client, _LATEST_UNREAD)
        params = parse_qs(urlsplit(href).query)
        assert json.loads(params["filters"][0]) == {"bookmark": "UNREAD"}, href
        assert params["orderBy"] == ["created_at"], href
        assert params["orderReverse"] == ["True"], href

    def test_latest_unread_does_not_inherit_keep_reading_filter(self) -> None:
        self._seed_reading()
        self.client.force_login(self.user)
        keep_reading = self._v1_href(self.client, _KEEP_READING)
        latest_unread = self._v1_href(self.client, _LATEST_UNREAD)
        self._v1(self.client, keep_reading)
        pks = _v1_comic_pks(self._v1(self.client, latest_unread))
        c = self.comics
        assert c[1].pk not in pks, pks  # finished
        bookmarked = set(
            Bookmark.objects.filter(user=self.user).values_list("comic_id", flat=True)
        )
        never_opened = {comic.pk for comic in c if comic.pk not in bookmarked}
        assert never_opened <= set(pks), pks

    def test_oldest_unread_is_ascending_after_latest_unread(self) -> None:
        # Dates run opposite to pk order so a pk tiebreak can't pass.
        for i, comic in enumerate(self.comics):
            Comic.objects.filter(pk=comic.pk).update(
                date=date(2000 + len(self.comics) - i, 1, 1)
            )
        self.client.force_login(self.user)
        latest_unread = self._v1_href(self.client, _LATEST_UNREAD)
        oldest_unread = self._v1_href(self.client, _OLDEST_UNREAD)
        self._v1(self.client, latest_unread)
        pks = _v1_comic_pks(self._v1(self.client, oldest_unread))
        dates = dict(Comic.objects.filter(pk__in=pks).values_list("pk", "date"))
        ordered = [dates[pk] for pk in pks]
        assert len(ordered) > 1, pks
        assert ordered == sorted(ordered), ordered

    def test_v1_root_links_match_v2_preview_groups(self) -> None:
        v2_links = {
            link.title: link
            for group in (*PREVIEW_GROUPS, FAVORITES_PREVIEW_GROUP)
            for link in group.links
        }
        shared = 0
        for top_link in (*RootTopLinks.ALL, RootTopLinks.FAVORITES):
            v2_link = v2_links.get(top_link.title)
            if not v2_link:
                continue
            shared += 1
            assert _sort_params(top_link.query_params) == _sort_params(
                v2_link.query_params
            ), top_link.title
        assert shared == len(RootTopLinks.ALL) + 1

    def test_favorites_entry_only_when_the_user_has_favorites(self) -> None:
        self.client.force_login(self.user)
        assert _v1_entry_href(self._v1(self.client), _FAVORITES) is None
        assert _v1_entry_href(self._v1(Client()), _FAVORITES) is None

        favorite = self.comics[3]
        Favorite.objects.create(
            user=self.user, collection="comics", target_id=favorite.pk
        )
        href = self._v1_href(self.client, _FAVORITES)
        assert _v1_entry_href(self._v1(Client()), _FAVORITES) is None
        assert _v1_comic_pks(self._v1(self.client, href)) == [favorite.pk]

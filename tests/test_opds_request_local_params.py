"""
An OPDS feed is a function of its URL, not of the links followed before it.

OPDS params were the saved ``SettingsBrowser`` row overlaid with the
request and saved back, so a link inherited whatever the last one set:
open a shelf, go back, open Publishers and the publishers were filtered
to that shelf; search, go back, open Latest Unread and it was narrowed to
the search. The row is per user, so one device's browsing changed
another's. These follow links the way a client does, without clearing
the feed cache in between (each URL is distinct, so nothing is served
from it).
"""

import json
from typing import Final
from urllib.parse import urlsplit

from codex.models import Comic, Imprint, Publisher, Series, Shelf, ShelfItem, Volume
from tests.test_opds_keep_reading import (
    _TEST_PASSWORD,
    _TMP_DIR,
    _V2_START,
    KeepReadingSeedTestCase,
    _group,
    _pks,
)

_HTTP_OK: Final = 200
_SHELF_NAME: Final = "Want to Read"
_LATEST_UNREAD: Final = "Latest Unread"


class OPDSRequestLocalParamsTestCase(KeepReadingSeedTestCase):
    """Links never inherit filters, search or a shelf from earlier ones."""

    def _login(self) -> None:
        assert self.client.login(username=self.user.username, password=_TEST_PASSWORD)

    def _get(self, url: str) -> dict:
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, (url, response.content[:300])
        return json.loads(response.content)

    @staticmethod
    def _local(href: str) -> str:
        split = urlsplit(href)
        return f"{split.path}?{split.query}" if split.query else split.path

    def _second_publisher(self) -> Publisher:
        """Make a publisher with one comic, on no shelf."""
        publisher = Publisher.objects.create(name="Other Pub")
        imprint = Imprint.objects.create(name="Other Imp", publisher=publisher)
        series = Series.objects.create(
            name="Other Ser", imprint=imprint, publisher=publisher
        )
        volume = Volume.objects.create(
            name="1", series=series, imprint=imprint, publisher=publisher
        )
        path = _TMP_DIR / "other.cbz"
        path.touch()
        Comic.objects.create(
            library=self.comics[0].library,
            path=path,
            issue_number=1,
            name="other",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            file_type="CBZ",
            page_count=3,
            size=1,
        )
        return publisher

    def _start_link(self, start: dict, title: str) -> str:
        """Return a start-page navigation or group link's href by title."""
        for item in start.get("navigation", []):
            if item.get("title") == title:
                return self._local(item["href"])
        group = _group(start, title)
        assert group is not None, title
        return self._local(group["links"][0]["href"])

    def _shelf(self) -> None:
        shelf = Shelf.objects.create(user=self.user, name=_SHELF_NAME)
        ShelfItem.objects.create(
            shelf=shelf, collection="comics", target_id=self.comics[0].pk
        )

    def _publisher_names(self, feed: dict) -> set[str]:
        return {link["title"] for link in feed.get("navigation", [])}

    def test_shelf_then_publishers_lists_every_publisher(self) -> None:
        other = self._second_publisher()
        self._shelf()
        self._login()
        start = self._get(_V2_START)
        self._get(self._start_link(start, _SHELF_NAME))

        publishers = self._get(self._start_link(start, "Publishers"))

        assert other.name in self._publisher_names(publishers), publishers

    def test_search_then_latest_unread_is_not_narrowed(self) -> None:
        self._login()
        start = self._get(_V2_START)
        self._get("/opds/v2.0/publishers?query=c1")

        latest = self._get(self._start_link(start, _LATEST_UNREAD))

        # Nothing is read yet, so every comic is unread.
        assert len(_pks(latest)) == len(self.comics), latest

    def test_search_then_shelf_lists_the_whole_shelf(self) -> None:
        self._shelf()
        self._login()
        start = self._get(_V2_START)
        self._get("/opds/v2.0/publishers?query=zzz-no-match")

        shelf_feed = self._get(self._start_link(start, _SHELF_NAME))

        pks = [
            int(link["href"].rstrip("/").split("/")[-2])
            for pub in shelf_feed.get("publications", [])
            for link in pub.get("links", [])
            if link.get("rel") == "http://opds-spec.org/progression"
        ]
        assert pks == [self.comics[0].pk], shelf_feed

"""
Reading Order, the automatic default, on list cards and under list filters.

On the lists grid there is no reading order across lists, so the cards
read by name, and each list's cover is its first issue. Under the Reading
Lists filter, a comic two ticked lists share is one comic: it must not
count twice in a card's pages and progress.
"""

import json
from decimal import Decimal
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client

from codex.models import Bookmark, ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_READING_ORDER: Final = "story_arc_number"


class ReadingOrderFixture(ReadingListFixture):
    """A signed-in reader sorting by Reading Order."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user(username="u", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()
        self.client.force_login(self.user)

    def make_list(self, name: str, comics) -> ReadingList:
        reading_list = ReadingList.objects.create(name=name)
        for position, comic in enumerate(comics):
            ReadingListEntry.objects.create(
                reading_list=reading_list,
                position=position,
                comic=comic,
                match_tier=ReadingListMatchTier.MANUAL,
            )
        return reading_list

    def browse(self, collection: str, settings: dict) -> dict:
        response = self.client.patch(
            f"/api/v4/browse/{collection}/settings",
            data=json.dumps({"orderBy": _READING_ORDER, **settings}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        response = self.client.get(f"/api/v4/browse/{collection}/0")
        assert response.status_code == _OK, response.content
        return response.json()["data"]


class ListCardsTests(ReadingOrderFixture):
    """The lists grid under Reading Order."""

    def test_cards_read_by_name(self) -> None:
        """Lists sort by name, not by the order they were made in."""
        c1, c2, _, _ = self.comics
        self.make_list("Zeta", [c1])
        self.make_list("Alpha", [c2])
        names = [card["name"] for card in self.browse("arcs", {})["collections"]]
        assert names == ["Alpha", "Zeta"]

    def test_a_cover_is_the_first_issue(self) -> None:
        """The cover is position 0, not the earliest-dated issue."""
        c1, _, c3, _ = self.comics
        assert c3.date > c1.date
        self.make_list("Event", [c3, c1])
        (card,) = self.browse("arcs", {})["collections"]
        assert card["coverPk"] == c3.pk


class SharedComicTests(ReadingOrderFixture):
    """Two ticked lists that share a comic count it once."""

    def test_progress_counts_a_shared_comic_once(self) -> None:
        """Nine pages read of three ten-page comics, not of four."""
        c1, c2, c3, _ = self.comics
        first = self.make_list("First", [c1, c2])
        second = self.make_list("Second", [c2, c3])
        Bookmark.objects.create(user=self.user, comic=c1, page=9)
        data = self.browse(
            "publishers", {"filters": {"readingLists": [first.pk, second.pk]}}
        )
        (card,) = data["collections"]
        # 9 * 100 / (30 - 1): three comics of ten pages.
        assert Decimal(str(card["progress"])) == Decimal("31.03")

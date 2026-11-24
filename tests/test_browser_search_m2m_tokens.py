"""
A search token on a many-to-many tag tests membership (C6 follow-up).

A field token with a glob, quotes or an operator, such as
``characters:*bat*``, is a database lookup rather than a full-text match.
On a many-to-many tag it was a plain ``characters__name`` lookup, an inline
join, so a comic holding two matching tags came back twice: two cards, a
count of two, and pages shifted. Before C6 any tag filter made the page
DISTINCT, which hid it then; with no tag filter it showed already. The token
is a membership test now, as the tag filters are: one row per comic. Each
term of an AND is its own test, so ``characters:(*batman* and *batgirl*)``
finds a comic holding both, where one joined row had to match both names.
"""

import json
from typing import Final, override

from cachalot.api import cachalot_disabled
from django.contrib.auth.models import User
from django.test import Client

from codex.models import Character, Credit, CreditPerson, CreditRole, Tag, Team
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200


class SearchManyToManyTokenTests(ReadingListFixture):
    """Four comics of one series; the first holds two of each matching tag."""

    @override
    def setUp(self) -> None:
        super().setUp()
        batman, batgirl, robin = (
            Character.objects.create(name=name)
            for name in ("Batman", "Batgirl", "Robin")
        )
        c1, c2, c3, _c4 = self.comics
        c1.characters.add(batman, batgirl)
        c2.characters.add(batman)
        c3.characters.add(robin)
        writer = CreditRole.objects.create(name="Writer")
        for name in ("Bob Kane", "Bob Haney"):
            person = CreditPerson.objects.create(name=name)
            c1.credits.add(Credit.objects.create(person=person, role=writer))
        c1.tags.add(*(Tag.objects.create(name=name) for name in ("batcave", "bats")))
        c1.teams.add(
            *(Team.objects.create(name=name) for name in ("Bat Family", "Bat Squad"))
        )
        self.batman = batman.pk  # pyright: ignore[reportUninitializedInstanceVariable]
        self.pks = [comic.pk for comic in self.comics]  # pyright: ignore[reportUninitializedInstanceVariable]
        admin = User.objects.create_user(
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client = Client()
        self.client.force_login(admin)
        self.series = c1.series_id  # pyright: ignore[reportUninitializedInstanceVariable]

    def _page(
        self, search: str, filters: dict | None = None, *, cached: bool = False
    ) -> tuple[list, int]:
        """Return the series page's comic pks, in order, and its count."""
        response = self.client.patch(
            "/api/v4/browse/series/settings",
            data=json.dumps(
                {"filters": filters or {}, "search": search, "orderBy": "sort_name"}
            ),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        if cached:
            response = self.client.get(f"/api/v4/browse/series/{self.series}")
        else:
            with cachalot_disabled():
                response = self.client.get(f"/api/v4/browse/series/{self.series}")
        assert response.status_code == _OK, response.content
        data = response.json()["data"]
        pks = [pk for book in data["books"] for pk in book["ids"]]
        return pks, data["count"]

    def _assert_once(self, search: str, expected: set[int], filters=None) -> None:
        pks, count = self._page(search, filters)
        assert sorted(pks) == sorted(expected), (search, pks)
        assert count == len(expected), (search, count)

    def test_a_token_matching_two_tags_finds_the_comic_once(self) -> None:
        c1, c2, _c3, _c4 = self.pks
        self._assert_once("characters:*bat*", {c1, c2})

    def test_with_a_tag_filter_too(self) -> None:
        c1, c2, _c3, _c4 = self.pks
        self._assert_once("characters:*bat*", {c1, c2}, {"characters": [self.batman]})

    def test_every_many_to_many_field(self) -> None:
        c1 = self.pks[0]
        for search in ("credits:*bob*", "tags:*bat*", "teams:*bat*"):
            with self.subTest(search=search):
                self._assert_once(search, {c1})

    def test_a_negated_token(self) -> None:
        """No character matches: the comics without one, once each."""
        c1, c2, c3, c4 = self.pks
        self._assert_once("not characters:*robin*", {c1, c2, c4})
        self._assert_once("not characters:*bat*", {c3, c4})
        self._assert_once(
            "not characters:*robin*", {c1, c2}, {"characters": [self.batman]}
        )

    def test_each_term_of_an_and_is_its_own_test(self) -> None:
        """A comic holding both, though no one character is named both."""
        c1 = self.pks[0]
        self._assert_once("characters:(*batman* and *batgirl*)", {c1})
        self._assert_once("characters:*batman* characters:*batgirl*", {c1})

    def test_or_finds_each_comic_once(self) -> None:
        c1, c2, c3, _c4 = self.pks
        self._assert_once("characters:(*batgirl* or *robin*)", {c1, c3})
        self._assert_once("characters:(*bat* or *robin*)", {c1, c2, c3})

    def test_a_new_tag_shows_in_the_next_request(self) -> None:
        """Cachalot tracks the subquery's tables, so the cached page goes."""
        c1, c2, c3, _c4 = self.pks
        assert sorted(self._page("characters:*bat*", cached=True)[0]) == [c1, c2]
        self.comics[2].characters.add(Character.objects.create(name="Batwoman"))
        assert sorted(self._page("characters:*bat*", cached=True)[0]) == [c1, c2, c3]

    def test_a_group_page(self) -> None:
        """On publishers, the token reaches comics through the group: one card."""
        response = self.client.patch(
            "/api/v4/browse/publishers/settings",
            data=json.dumps({"filters": {}, "search": "characters:*bat*"}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        with cachalot_disabled():
            response = self.client.get("/api/v4/browse/publishers/0")
        assert response.status_code == _OK, response.content
        data = response.json()["data"]
        publisher = self.comics[0].publisher_id
        assert [group["ids"] for group in data["collections"]] == [[publisher]]
        assert data["collections"][0]["childCount"] == 2  # noqa: PLR2004

"""
Filters set to All: a comic must hold every ticked value.

Each ticked value is its own ``IN`` subquery, ANDed, never a join, so a
comic holding several ticked values is one row and sums stay per comic.
The reader's next and previous follow the same filters.
"""

import json
from typing import Final, override

from django.contrib.auth.models import User

from codex.choices.browser import VUETIFY_NULL_CODE
from codex.librarian.scribe.readinglists.live import add_item, reconcile_list
from codex.models import Comic, ReadingList
from codex.views.readinglists.entries import add_comics
from tests.test_browser_filter_choices_ticked import TickedFixture

_OK: Final = 200
_PW: Final = "test-pw-hush-S106"
_ALL_CHARACTERS: Final = {"matchAll": ["characters"]}
_ALL_LISTS: Final = {"matchAll": ["readingLists"]}


class MatchAllFixture(TickedFixture):
    """The ticked-choices fixture: Spindle-Man on c1; Iron Marshal on c1 and c2."""

    def characters(self, *characters, every: bool) -> dict:
        filters: dict = {"characters": [c.pk for c in characters]}
        if every:
            filters.update(_ALL_CHARACTERS)
        return filters

    def reader_next(self, comic: Comic) -> int | None:
        arc = {"collection": "series", "ids": [self.series.pk]}
        response = self.client.get(
            f"/api/v4/reader/comics/{comic.pk}", {"arc": json.dumps(arc)}
        )
        assert response.status_code == _OK, response.content
        following = response.json()["data"]["books"].get("next")
        return following["pk"] if following else None


class MatchAllTagTests(MatchAllFixture):
    """Characters set to All."""

    def test_any_is_either(self) -> None:
        """The default: a comic with any ticked character."""
        c1, c2, _, _ = self.comics
        filters = self.characters(self.spidey, self.iron, every=False)
        assert self.listed(filters) == {c1.pk, c2.pk}

    def test_all_is_both(self) -> None:
        """Only the comic with Spindle-Man and Iron Marshal."""
        filters = self.characters(self.spidey, self.iron, every=True)
        assert self.listed(filters) == {self.comics[0].pk}

    def test_all_of_one_is_that_one(self) -> None:
        """One ticked value: All and Any agree."""
        c1, c2, _, _ = self.comics
        filters = self.characters(self.iron, every=True)
        assert self.listed(filters) == {c1.pk, c2.pk}

    def test_all_with_none_and_a_value_is_nothing(self) -> None:
        """No comic has no character and a character."""
        filters = {"characters": [VUETIFY_NULL_CODE, self.iron.pk], **_ALL_CHARACTERS}
        assert self.listed(filters) == set()

    def test_all_with_only_none(self) -> None:
        """None alone is the comics with no character, as under Any."""
        any_none = self.listed({"characters": [VUETIFY_NULL_CODE]})
        assert any_none
        all_none = self.listed({"characters": [VUETIFY_NULL_CODE], **_ALL_CHARACTERS})
        assert all_none == any_none

    def test_sums_stay_per_comic(self) -> None:
        """A comic with both ticked characters counts once."""
        filters = self.characters(self.spidey, self.iron, every=True)
        response = self.client.get(
            f"/api/v4/browse/series/{self.series.pk}/metadata",
            {"filters": json.dumps(filters), "search": ""},
        )
        assert response.status_code == _OK, response.content
        data = response.json()["data"]
        assert (data["childCount"], data["pageCount"]) == (1, 10), data

    def test_a_cached_browse_follows_a_tag_change(self) -> None:
        """Iron Marshal joins Spindle-Man on c2: it shows without a cache clear."""
        c1, c2, _, _ = self.comics
        filters = self.characters(self.spidey, self.iron, every=True)
        assert self.listed(filters) == {c1.pk}
        c2.characters.add(self.spidey)
        assert self.listed(filters) == {c1.pk, c2.pk}

    def test_the_reader_follows_all(self) -> None:
        """Under Any c1's next is c2; under All nothing else matches."""
        c1, c2, _, _ = self.comics
        self.listed(self.characters(self.spidey, self.iron, every=False))
        assert self.reader_next(c1) == c2.pk
        self.listed(self.characters(self.spidey, self.iron, every=True))
        assert self.reader_next(c1) is None


class MatchAllListsTests(MatchAllFixture):
    """Reading Lists set to All, off the grid of lists."""

    @override
    def setUp(self) -> None:
        super().setUp()
        c1, c2, c3, _ = self.comics
        self.first = ReadingList.objects.create(name="First", user=self.reader)  # pyright: ignore[reportUninitializedInstanceVariable]
        add_comics(self.first, [c1.pk, c2.pk])
        self.second = ReadingList.objects.create(name="Second", user=self.reader)  # pyright: ignore[reportUninitializedInstanceVariable]
        add_comics(self.second, [c2.pk, c3.pk])

    def test_any_is_either_list(self) -> None:
        c1, c2, c3, _ = self.comics
        filters = {"readingLists": [self.first.pk, self.second.pk]}
        assert self.listed(filters) == {c1.pk, c2.pk, c3.pk}

    def test_all_is_on_both_lists(self) -> None:
        filters = {"readingLists": [self.first.pk, self.second.pk], **_ALL_LISTS}
        assert self.listed(filters) == {self.comics[1].pk}

    def test_another_users_list_holds_nothing(self) -> None:
        """A list the viewer may not see is on no comic of theirs."""
        other = User.objects.create_user(username="other", password=_PW)
        theirs = ReadingList.objects.create(name="Theirs", user=other)
        add_comics(theirs, [self.comics[1].pk])
        filters = {"readingLists": [self.first.pk, theirs.pk], **_ALL_LISTS}
        assert self.listed(filters) == set()

    def test_all_with_none_and_a_list_is_nothing(self) -> None:
        filters = {"readingLists": [VUETIFY_NULL_CODE, self.first.pk], **_ALL_LISTS}
        assert self.listed(filters) == set()


class MatchAllGridTests(MatchAllFixture):
    """On the grid of lists, All shows the lists every ticked list holds."""

    @override
    def setUp(self) -> None:
        super().setUp()
        c1, c2, c3, _ = self.comics
        self.held = {}  # pyright: ignore[reportUninitializedInstanceVariable]
        for name, comic in (("X", c1), ("Y", c2), ("Z", c3)):
            held = ReadingList.objects.create(name=name, user=self.reader)
            add_comics(held, [comic.pk])
            self.held[name] = held
        self.holder_a = self._holder("A", ("X", "Y"))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.holder_b = self._holder("B", ("Y", "Z"))  # pyright: ignore[reportUninitializedInstanceVariable]

    def _holder(self, name: str, held: tuple[str, ...]) -> ReadingList:
        holder = ReadingList.objects.create(name=name, user=self.reader)
        for held_name in held:
            add_item(holder, "arcs", self.held[held_name].pk)
        reconcile_list(holder)
        return holder

    def _grid(self, filters: dict) -> set[str]:
        data = self.browse("arcs", filters)
        return {row["name"] for row in data["collections"]}

    def test_any_is_what_either_holds(self) -> None:
        filters = {"readingLists": [self.holder_a.pk, self.holder_b.pk]}
        assert self._grid(filters) == {"X", "Y", "Z"}

    def test_all_is_what_both_hold(self) -> None:
        filters = {
            "readingLists": [self.holder_a.pk, self.holder_b.pk],
            **_ALL_LISTS,
        }
        assert self._grid(filters) == {"Y"}


class MatchAllChoicesTests(MatchAllFixture):
    """Under All a filter's own ticks narrow its list to what still occurs."""

    def test_any_leaves_its_own_list_whole(self) -> None:
        """The Phase 1 rule, unchanged under Any."""
        filters = self.characters(self.spidey, every=False)
        assert self.names("characters", filters) == {
            "Spindle-Man",
            "Iron Marshal",
            "Woodvole",
            "_none_",
        }

    def test_all_offers_what_occurs_with_the_ticked(self) -> None:
        """Spindle-Man ticked under All: only his co-star is left to add."""
        filters = self.characters(self.spidey, every=True)
        assert self.names("characters", filters) == {"Spindle-Man", "Iron Marshal"}

    def test_a_ticked_value_is_still_listed_under_all(self) -> None:
        """Ticked values that no comic holds together still show."""
        filters = self.characters(self.spidey, self.woodvole, every=True)
        assert self.names("characters", filters) == {"Spindle-Man", "Woodvole"}

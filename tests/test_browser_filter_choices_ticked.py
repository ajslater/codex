"""
A filter's choices with values ticked in it.

Several values in one filter match any of them, so a filter's own value
does not narrow its own choices; the other filters still do. A ticked
value is always listed, so it can be unticked, but it is named only
through what the viewer may see: never a tag found only on a hidden
comic, never another user's list.
"""

import json
from typing import Final, override

from django.contrib.auth.models import Group, User

from codex.choices.browser import DUMMY_NULL_NAME, VUETIFY_NULL_CODE
from codex.models import Comic, Library, ReadingList
from codex.models.age_rating import AgeRating, AgeRatingMetron
from codex.models.auth import GroupAuth
from codex.models.named import Character
from codex.views.readinglists.entries import add_comics
from tests.test_reading_list_filter_items import FilterFixture
from tests.test_reading_lists import TMP_DIR

_OK: Final = 200
_PW: Final = "test-pw-hush-S106"
_NONE: Final = DUMMY_NULL_NAME


class TickedFixture(FilterFixture):
    """
    Characters on the four Civil War comics, and one on a hidden comic.

    Spindle-Man and Iron Marshal on the first, Iron Marshal on the second,
    Woodvole on the third, none on the fourth. The reader's own list
    holds the third. Captain Marlow is only on a comic in a library the
    reader may not see.
    """

    @override
    def setUp(self) -> None:
        super().setUp()
        c1, c2, c3, c4 = self.comics
        self.spidey = Character.objects.create(name="Spindle-Man")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.iron = Character.objects.create(name="Iron Marshal")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.woodvole = Character.objects.create(name="Woodvole")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.marlow = Character.objects.create(name="Captain Marlow")  # pyright: ignore[reportUninitializedInstanceVariable]
        c1.characters.add(self.spidey, self.iron)
        c2.characters.add(self.iron)
        c3.characters.add(self.woodvole)
        Comic.objects.filter(pk=c4.pk).update(year=2010)
        add_comics(self.mine, [c3.pk])
        self._hidden_comic().characters.add(self.marlow)

    def _hidden_comic(self) -> Comic:
        """Make a comic of the series in a library no group of the reader's sees."""
        hidden_dir = TMP_DIR / "hidden"
        hidden_dir.mkdir(parents=True, exist_ok=True)
        library = Library.objects.create(path=str(hidden_dir))
        group = Group.objects.create(name="nobody here")
        GroupAuth.objects.create(group=group)
        library.groups.add(group)
        path = hidden_dir / "h.cbz"
        path.touch()
        first = self.comics[0]
        return Comic.objects.create(
            library=library,
            path=path,
            name="Hidden",
            issue_number=5,
            year=2006,
            publisher=first.publisher,
            imprint=first.imprint,
            series=first.series,
            volume=first.volume,
            size=1,
        )

    def choices(self, field: str, filters: dict) -> list[dict]:
        params = {"filters": json.dumps(filters), "search": ""}
        response = self.client.get(
            f"/api/v4/browse/series/{self.series.pk}/choices/{field}", params
        )
        assert response.status_code == _OK, response.content
        return response.json()["data"]["choices"]

    def names(self, field: str, filters: dict) -> set[str]:
        return {str(row["name"]) for row in self.choices(field, filters)}


class OwnFilterTests(TickedFixture):
    """A filter's own value leaves its own list whole; the others narrow."""

    def test_nothing_ticked(self) -> None:
        """Every character of the series the reader may see, and None."""
        assert self.names("characters", {}) == {
            "Spindle-Man",
            "Iron Marshal",
            "Woodvole",
            _NONE,
        }

    def test_its_own_value_does_not_narrow(self) -> None:
        """Spindle-Man ticked: the others are still offered."""
        filters = {"characters": [self.spidey.pk]}
        assert self.names("characters", filters) == {
            "Spindle-Man",
            "Iron Marshal",
            "Woodvole",
            _NONE,
        }

    def test_another_filter_narrows(self) -> None:
        """The reader's list holds the third comic: only Woodvole."""
        filters = {"reading_lists": [self.mine.pk]}
        assert self.names("characters", filters) == {"Woodvole"}

    def test_its_own_list_is_narrowed_by_the_others(self) -> None:
        """Characters ticked, the list filter's choices follow them."""
        filters = {"characters": [self.woodvole.pk]}
        assert self.names("reading_lists", filters) == {"Mine"}
        filters = {"characters": [self.spidey.pk], "reading_lists": [self.mine.pk]}
        assert self.names("reading_lists", filters) == {"Mine", _NONE}


class TickedIsListedTests(TickedFixture):
    """A ticked value shows even when the other filters leave it no comic."""

    def test_a_ticked_value_with_no_comic_here(self) -> None:
        """Spindle-Man is on no comic of the list, and still listed."""
        filters = {"reading_lists": [self.mine.pk], "characters": [self.spidey.pk]}
        assert self.names("characters", filters) == {"Woodvole", "Spindle-Man"}

    def test_a_ticked_none(self) -> None:
        """None ticked where every comic left has a character."""
        filters = {"reading_lists": [self.mine.pk], "characters": [VUETIFY_NULL_CODE]}
        assert self.names("characters", filters) == {"Woodvole", _NONE}

    def test_a_ticked_plain_value(self) -> None:
        """A year no comic in the list has is echoed."""
        filters = {"reading_lists": [self.mine.pk], "year": [2010]}
        assert set(self.choices("year", filters)) == {2006, 2010}

    def test_a_ticked_list_with_no_comic_here(self) -> None:
        """A list of the reader's that holds nothing left is still listed."""
        other = ReadingList.objects.create(name="Other", user=self.reader)
        add_comics(other, [self.comics[0].pk])
        filters = {"characters": [self.woodvole.pk], "reading_lists": [other.pk]}
        assert self.names("reading_lists", filters) == {"Mine", "Other"}

    def test_a_ticked_list_none(self) -> None:
        """None ticked where every comic left is on a list."""
        filters = {
            "characters": [self.woodvole.pk],
            "reading_lists": [VUETIFY_NULL_CODE],
        }
        assert self.names("reading_lists", filters) == {"Mine", _NONE}


class TickedIsNotLeakedTests(TickedFixture):
    """A ticked pk names nothing the reader may not see."""

    def test_a_tag_only_on_a_hidden_comic(self) -> None:
        """Captain Marlow is on no comic the reader may see."""
        filters = {"characters": [self.marlow.pk]}
        names = self.names("characters", filters)
        assert "Captain Marlow" not in names
        assert names == {"Spindle-Man", "Iron Marshal", "Woodvole", _NONE}

    def test_another_users_list(self) -> None:
        """Another user's personal list is never named."""
        other = User.objects.create_user(username="other", password=_PW)
        theirs = ReadingList.objects.create(name="Theirs", user=other)
        add_comics(theirs, [self.comics[0].pk])
        filters = {"reading_lists": [theirs.pk]}
        assert "Theirs" not in self.names("reading_lists", filters)


class AgeRatingPairTests(TickedFixture):
    """The two Age Rating tabs leave out their own key only."""

    @override
    def setUp(self) -> None:
        super().setUp()
        c1, c2, _, _ = self.comics
        teen = AgeRatingMetron.objects.get(name="Teen")
        everyone = AgeRatingMetron.objects.get(name="Everyone")
        self.teen_metron = teen  # pyright: ignore[reportUninitializedInstanceVariable]
        self.teen = AgeRating.objects.create(name="T", metron=teen)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.everyone = AgeRating.objects.create(name="E", metron=everyone)  # pyright: ignore[reportUninitializedInstanceVariable]
        Comic.objects.filter(pk=c1.pk).update(
            age_rating=self.teen, age_rating_metron_index=teen.index
        )
        Comic.objects.filter(pk=c2.pk).update(
            age_rating=self.everyone, age_rating_metron_index=everyone.index
        )

    def test_a_tagged_tick_narrows_the_metron_tab(self) -> None:
        """The As-tagged "T" ticked: only Teen is Standardized."""
        filters = {"age_rating_tagged": [self.teen.pk]}
        assert self.names("age_rating_metron", filters) == {"Teen"}

    def test_a_tagged_tick_leaves_its_own_tab_whole(self) -> None:
        """The As-tagged tab still offers every tagged rating."""
        filters = {"age_rating_tagged": [self.teen.pk]}
        assert self.names("age_rating_tagged", filters) == {"T", "E", _NONE}

    def test_a_ticked_metron_rating_keeps_rating_order(self) -> None:
        """A ticked rating with no comic here is listed in rating order."""
        adult = AgeRatingMetron.objects.get(name="Adult")
        rating = AgeRating.objects.create(name="A", metron=adult)
        Comic.objects.filter(pk=self.comics[3].pk).update(
            age_rating=rating, age_rating_metron_index=adult.index
        )
        filters = {
            "reading_lists": [self.mine.pk],
            "age_rating_metron": [adult.pk, self.teen_metron.pk],
        }
        rows = self.choices("age_rating_metron", filters)
        assert [row["name"] for row in rows if row["pk"] != VUETIFY_NULL_CODE] == [
            "Teen",
            "Adult",
        ]

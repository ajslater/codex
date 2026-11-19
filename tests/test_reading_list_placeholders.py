"""
Missing issues show in the grid at their places.

Inside one list, in Reading Order, with no search or filter, the page
carries the list's missing issues that fall on it: after the previous
page's last comic, through its own last comic. Reversed order mirrors it.
"""

import json
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag, ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_PAGE_SIZE: Final = 2


class PlaceholderFixture(ReadingListFixture):
    """Four comics at odd places; missing issues around them; one hidden."""

    @override
    def setUp(self) -> None:
        super().setUp()
        AdminFlag.objects.update_or_create(
            key=AdminFlagChoices.BROWSER_MAX_OBJ_PER_PAGE.value,
            defaults={"value": str(_PAGE_SIZE)},
        )
        cache.clear()
        self.reading_list = ReadingList.objects.create(name="Event")  # pyright: ignore[reportUninitializedInstanceVariable]
        c1, c2, c3, c4 = self.comics
        rows = (
            (None, "Prelude", False),
            (c1, "", False),
            (None, "Tie-In A", False),
            (c2, "", False),
            (None, "Skipped", True),
            (c3, "", False),
            (None, "Tie-In B", False),
            (c4, "", False),
            (None, "Epilogue", False),
        )
        for position, (comic, series, ignored) in enumerate(rows):
            ReadingListEntry.objects.create(
                reading_list=self.reading_list,
                position=position,
                comic=comic,
                ignored=ignored,
                series_name=series,
                issue="1" if series else "",
                year=2006,
                entry_type="tie-in" if series.startswith("Tie") else "",
                match_tier=ReadingListMatchTier.MANUAL
                if comic
                else ReadingListMatchTier.NONE,
            )
        self.client = Client()
        self.client.force_login(User.objects.create_user(username="u", password=_PW))

    def _page(self, page: int = 1, **params) -> dict:
        query = {
            "page": page,
            "order_by": "story_arc_number",
            "order_reverse": "false",
            "filters": json.dumps({}),
            "search": "",
            **params,
        }
        url = f"/api/v4/browse/arcs/{self.reading_list.pk}"
        response = self.client.get(url, query)
        assert response.status_code == _OK, response.content
        return response.json()["data"]

    @staticmethod
    def _missing(data: dict) -> list[tuple[int, str]]:
        return [
            (entry["position"], entry["seriesName"])
            for entry in data.get("missingEntries") or ()
        ]


class PlaceholderTests(PlaceholderFixture):
    """Each page carries the missing issues between its comics."""

    def test_the_first_page_starts_at_the_list_start(self) -> None:
        """Page 1 holds the prelude and the tie-in before its last comic."""
        data = self._page(1)
        assert [int(book["orderValue"]) for book in data["books"]] == [1, 3]
        assert self._missing(data) == [(0, "Prelude"), (2, "Tie-In A")]
        assert data["missingCount"] == 4  # noqa: PLR2004

    def test_the_last_page_runs_to_the_end(self) -> None:
        """Page 2 holds what follows page 1's last comic; the hidden entry never."""
        data = self._page(2)
        assert self._missing(data) == [(6, "Tie-In B"), (8, "Epilogue")]

    def test_reversed_mirrors_it(self) -> None:
        """Newest first: page 1 runs from the end to its last comic."""
        data = self._page(1, order_reverse="true")
        assert [int(book["orderValue"]) for book in data["books"]] == [7, 5]
        assert self._missing(data) == [(8, "Epilogue"), (6, "Tie-In B")]
        data = self._page(2, order_reverse="true")
        assert self._missing(data) == [(2, "Tie-In A"), (0, "Prelude")]

    def test_only_editors_get_the_menu(self) -> None:
        """A global list is an admin's to edit, not a reader's."""
        assert self._page(1)["missingEditable"] is False
        admin = User.objects.create_user(username="admin", password=_PW, is_staff=True)
        self.client.force_login(admin)
        assert self._page(1)["missingEditable"] is True

    def test_an_entry_carries_what_the_card_shows(self) -> None:
        """Series, issue, year and type, and the entry pk for its menu."""
        entry = self._page(1)["missingEntries"][1]
        assert entry["issue"] == "1"
        assert entry["year"] == 2006  # noqa: PLR2004
        assert entry["entryType"] == "tie-in"
        assert ReadingListEntry.objects.get(pk=entry["pk"]).position == 2  # noqa: PLR2004


class NoPlaceholderTests(PlaceholderFixture):
    """Only Reading Order inside one list, with no search or filter."""

    def test_another_order_has_none(self) -> None:
        """Sorted by name, a missing issue has no place."""
        assert not self._page(1, order_by="sort_name").get("missingEntries")

    def test_a_filter_has_none(self) -> None:
        """A filtered list leaves its missing issues out."""
        data = self._page(1, filters=json.dumps({"bookmark": "UNREAD"}))
        assert not data.get("missingEntries")

    def test_a_search_has_none(self) -> None:
        """A search is not the list."""
        data = self._page(1, search="civil")
        assert not data.get("missingEntries")

    def test_the_setting_turns_them_off(self) -> None:
        """Show Missing Issues off sends none."""
        data = self._page(1, show_missing_issues="false")
        assert not data.get("missingEntries")


class ReadingOrderRowTests(PlaceholderFixture):
    """Table rows in Reading Order carry their place."""

    def test_rows_carry_positions(self) -> None:
        """Each comic row says where it sits in the list."""
        data = self._page(1, view_mode="table", columns="cover,name")
        assert [row["position"] for row in data["rows"]] == [1, 3]
        assert self._missing(data) == [(0, "Prelude"), (2, "Tie-In A")]

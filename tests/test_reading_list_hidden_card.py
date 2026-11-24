"""
A hidden entry gives its list no cover and no table cells (B3).

The card's cover subquery and the table view's intersections joined a
list's entries without ``ignored=False``, so a hidden comic could cover the
list and blank or skew its row's shared values.
"""

import json
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client

from codex.models import Comic, Genre, ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_SHOW_ALL: Final = {
    "publishers": True,
    "imprints": True,
    "series": True,
    "volumes": True,
}


class HiddenEntryCardTests(ReadingListFixture):
    """A hidden entry gives its list no cover and no table cells."""

    @override
    def setUp(self) -> None:
        super().setUp()
        # The earliest comic, which the cover order would pick, is hidden.
        hidden, *shown = self.comics[:3]
        self.hidden = hidden  # pyright: ignore[reportUninitializedInstanceVariable]
        self.reading_list = ReadingList.objects.create(name="Shared")  # pyright: ignore[reportUninitializedInstanceVariable]
        for position, comic in enumerate(self.comics[:3]):
            ReadingListEntry.objects.create(
                reading_list=self.reading_list,
                position=position,
                comic=comic,
                match_tier=ReadingListMatchTier.MANUAL,
                ignored=comic is hidden,
            )
        Comic.objects.filter(pk=hidden.pk).update(year=1990)
        genre = Genre.objects.create(name="Event")
        for comic in shown:
            comic.genres.add(genre)
        self.client = Client()
        self.client.force_login(User.objects.create_user(username="u", password=_PW))

    def test_no_card_cover_from_it(self) -> None:
        """The list's card is covered by a shown comic."""
        response = self.client.get(
            "/api/v4/browse/arcs/0",
            {"filters": json.dumps({}), "show": json.dumps(_SHOW_ALL)},
        )
        assert response.status_code == _OK, response.content
        (card,) = response.json()["data"]["collections"]
        assert card["coverPk"] != self.hidden.pk
        assert card["coverPk"] in {comic.pk for comic in self.comics[1:3]}

    def test_no_table_cells_from_it(self) -> None:
        """The list's row shares the year and genre of its shown comics."""
        response = self.client.patch(
            "/api/v4/browse/arcs/settings",
            data=json.dumps({"viewMode": "table"}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        response = self.client.get(
            "/api/v4/browse/arcs/0", {"page": 1, "columns": "cover,name,year,genres"}
        )
        assert response.status_code == _OK, response.content
        (row,) = response.json()["data"]["rows"]
        assert (row["year"], row["genres"]) == (2006, ["Event"])

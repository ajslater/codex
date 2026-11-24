"""
A reading list's details, Continue Reading and Export Missing.

The details tell a viewer what the list is and how much of it they have:
its type, curator, years and sources, "31 of 98 in library, 12 read", the
lists before and after it, and the first issue they have not finished.
"""

import json
from typing import Final, override

from comicbox.readinglists import loads
from django.contrib.auth.models import User
from django.test import Client

from codex.models import (
    Bookmark,
    Genre,
    ReadingList,
    ReadingListEntry,
    ReadingListSource,
)
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from codex.views.readinglists.details import continue_blocked
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200


class ListDetailsFixture(ReadingListFixture):
    """An imported list of six: four comics, two missing; one comic read."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user(username="reader", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.prequel = ReadingList.objects.create(name="House of M")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.reading_list = ReadingList.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Civil War",
            description="Heroes take sides.",
            list_type="event",
            start_year=2006,
            end_year=2007,
            extra={
                "previous": {"name": "House of M"},
                "next": {"name": "Secret Invasion"},
            },
        )
        ReadingListSource.objects.create(
            reading_list=self.reading_list,
            kind=ReadingListSourceKind.CATALOG,
            ref="Marvel/Civil War.cbl",
            attribution_source="cbro",
            attribution_url="https://cbro.invalid/civil-war",
        )
        c1, c2, c3, c4 = self.comics
        rows = (c1, None, c2, c3, None, c4)
        for position, comic in enumerate(rows):
            ReadingListEntry.objects.create(
                reading_list=self.reading_list,
                position=position,
                comic=comic,
                series_name="Civil War" if comic else "Front Line",
                issue=str(position),
                year=2006,
                reference={
                    "series": {"name": "Civil War" if comic else "Front Line"},
                    "issue": {"name": str(position)},
                    "date": {"year": 2006},
                },
                match_tier=ReadingListMatchTier.MANUAL
                if comic
                else ReadingListMatchTier.NONE,
            )
        Bookmark.objects.create(user=self.user, comic=c1, page=9, finished=True)
        Bookmark.objects.create(user=self.user, comic=c2, page=4, finished=False)
        self.client = Client()
        self.client.force_login(self.user)

    def _details(self) -> dict:
        params = {"filters": json.dumps({}), "search": ""}
        url = f"/api/v4/browse/arcs/{self.reading_list.pk}/metadata"
        response = self.client.get(url, params)
        assert response.status_code == _OK, response.content
        return response.json()["data"]["readingListDetails"]


class ListDetailsTests(ListDetailsFixture):
    """What the details say about a list."""

    def test_the_header(self) -> None:
        """Description, type, years and the curator with a link."""
        details = self._details()
        assert details["description"] == "Heroes take sides."
        assert details["listType"] == "event"
        assert (details["startYear"], details["endYear"]) == (2006, 2007)
        (source,) = details["sources"]
        assert source["label"] == "DieselTech Catalog"
        assert source["attribution"] == "cbro"
        assert source["attributionUrl"] == "https://cbro.invalid/civil-war"

    def test_uploads_are_named_by_their_file(self) -> None:
        """Two uploads would both read "Upload": each names its file."""
        ReadingListSource.objects.create(
            reading_list=self.reading_list,
            kind=ReadingListSourceKind.UPLOAD,
            ref="Civil War (2006).cbl",
            rank=1,
        )
        labels = [source["label"] for source in self._details()["sources"]]
        assert labels == ["DieselTech Catalog", "Upload Civil War (2006).cbl"]

    def test_how_much_is_here_and_read(self) -> None:
        """Four of six in the library, one read."""
        details = self._details()
        assert (details["inLibrary"], details["total"], details["read"]) == (4, 6, 1)
        assert details["missing"] == 2  # noqa: PLR2004

    def test_neighbours_link_when_imported(self) -> None:
        """The previous list is here, the next one is not."""
        details = self._details()
        assert details["previous"] == {"pk": self.prequel.pk, "name": "House of M"}
        assert details["next"] == {"pk": None, "name": "Secret Invasion"}

    def test_continue_is_the_first_unfinished_issue(self) -> None:
        """#1 is read; the next is #2 at its bookmarked page."""
        details = self._details()
        assert details["continue"] == {"pk": self.comics[1].pk, "page": 4}

    def test_anonymous_viewers_see_the_details(self) -> None:
        """Anyone who sees the list sees what it is."""
        self.client.logout()
        details = self._details()
        assert details["total"] == 6  # noqa: PLR2004
        assert details["read"] == 0
        assert details["editable"] is False


class ContinueEndpointTests(ListDetailsFixture):
    """The card menu asks where to continue."""

    def test_continue(self) -> None:
        """The first unfinished comic, in list order."""
        response = self.client.get(
            f"/api/v4/reading-lists/{self.reading_list.pk}/continue"
        )
        assert response.status_code == _OK, response.content
        assert response.json()["data"]["continue"] == {
            "pk": self.comics[1].pk,
            "page": 4,
        }

    def test_nothing_when_all_are_read(self) -> None:
        """A finished list has nowhere to continue."""
        for comic in self.comics:
            Bookmark.objects.update_or_create(
                user=self.user, comic=comic, defaults={"finished": True}
            )
        response = self.client.get(
            f"/api/v4/reading-lists/{self.reading_list.pk}/continue"
        )
        assert response.json()["data"]["continue"] is None


class ContinueFilterTests(ListDetailsFixture):
    """Continue Reading skips a comic the browser's filters leave out."""

    @override
    def setUp(self) -> None:
        super().setUp()
        genre = Genre.objects.create(name="Event")
        c1, _, c3, c4 = self.comics
        for comic in (c1, c3, c4):
            comic.genres.add(genre)
        self.filters = {"genres": [genre.pk]}  # pyright: ignore[reportUninitializedInstanceVariable]
        response = self.client.patch(
            "/api/v4/browse/arcs/settings",
            data=json.dumps({"filters": self.filters}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content

    def _reads(self, comic_pk: int) -> int:
        """Open the comic in the reader through this list."""
        arc = {"collection": "arcs", "ids": [self.reading_list.pk]}
        response = self.client.get(
            f"/api/v4/reader/comics/{comic_pk}", {"arc": json.dumps(arc)}
        )
        return response.status_code

    def test_the_endpoint_skips_a_filtered_comic(self) -> None:
        """#2 is filtered out, so Continue is #3, which the reader opens."""
        response = self.client.get(
            f"/api/v4/reading-lists/{self.reading_list.pk}/continue"
        )
        assert response.status_code == _OK, response.content
        found = response.json()["data"]["continue"]
        assert found == {"pk": self.comics[2].pk, "page": 0}
        assert self._reads(found["pk"]) == _OK

    def test_the_details_skip_a_filtered_comic(self) -> None:
        """The metadata dialog's Continue follows the same filters."""
        params = {"filters": json.dumps(self.filters), "search": ""}
        url = f"/api/v4/browse/arcs/{self.reading_list.pk}/metadata"
        response = self.client.get(url, params)
        assert response.status_code == _OK, response.content
        found = response.json()["data"]["readingListDetails"]["continue"]
        assert found == {"pk": self.comics[2].pk, "page": 0}


class ContinueBlockedTests(ListDetailsFixture):
    """With nowhere to continue, the details say why, so the hint is true."""

    def _blocked(self, filters: dict | None = None) -> tuple:
        params = {"filters": json.dumps(filters or {}), "search": ""}
        url = f"/api/v4/browse/arcs/{self.reading_list.pk}/metadata"
        response = self.client.get(url, params)
        assert response.status_code == _OK, response.content
        details = response.json()["data"]["readingListDetails"]
        return details["continue"], details["continueBlocked"]

    def test_a_list_with_somewhere_to_go_is_not_blocked(self) -> None:
        assert self._blocked() == ({"pk": self.comics[1].pk, "page": 4}, "")

    def test_every_issue_read(self) -> None:
        for comic in self.comics:
            Bookmark.objects.update_or_create(
                user=self.user, comic=comic, defaults={"finished": True}
            )
        assert self._blocked() == (None, "all_read")

    def test_no_issue_in_the_library(self) -> None:
        """
        Said by the rule itself: no metadata dialog opens on such a list.

        The browse metadata of a list with no comic in the library is a 404.
        """
        assert continue_blocked([], {}, None) == "none_in_library"

    def test_the_filters_hide_every_unread_issue(self) -> None:
        genre = Genre.objects.create(name="Read Only")
        self.comics[0].genres.add(genre)
        assert self._blocked({"genres": [genre.pk]}) == (None, "filtered")


class ExportMissingTests(ListDetailsFixture):
    """Export Missing writes only the issues the library lacks."""

    def test_export_missing(self) -> None:
        """Two missing issues, as a list to hunt with."""
        response = self.client.get(
            f"/api/v4/reading-lists/{self.reading_list.pk}/export",
            {"fmt": "cbl", "missing": "1"},
        )
        assert response.status_code == _OK, response.content
        entries = loads(response.content).reading_list["entries"]
        assert [entry["series"]["name"] for entry in entries] == [
            "Front Line",
            "Front Line",
        ]

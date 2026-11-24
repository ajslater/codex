"""
List rows group by their key, not by every column, and lose DISTINCT (C4).

The lists grid grouped a list's rows by every ReadingList column, text
blobs included, and selected them DISTINCT. It groups by the key now, and
once the card aggregates group the page query, each list is one row, so
the DISTINCT goes there. These tests run the grid both ways, the old shape
forced and the new, on lists built to tell them apart, and get the same
cards in the same order with the same counts: by name, in reading order and
by child count, under a search, in table view, with a missing comic, and
for a viewer who is not signed in.
"""

import json
from typing import Final, override
from unittest.mock import patch

from cachalot.api import cachalot_disabled
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag, ReadingList, ReadingListEntry
from codex.models.comic import ComicFTS
from codex.models.readinglist import ReadingListMatchTier
from codex.views.browser.annotate import card
from codex.views.browser.annotate.card import BrowserAnnotateCardView
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_FIELDS: Final = ("pk", "name", "childCount", "finished", "progress", "coverPk")
_OLD_GROUP_BY: Final = {
    model: fields
    for model, fields in card._COLLECTION_BY.items()  # noqa: SLF001
    if model is not ReadingList
}


class ListRowsTests(ReadingListFixture):
    """Same-named lists, shared comics, a repeat, a hidden entry, another user."""

    @override
    def setUp(self) -> None:
        super().setUp()
        c1, c2, c3, c4 = self.comics
        user = User.objects.create_user(username="u", password=_PW)
        other = User.objects.create_user(username="other", password=_PW)
        for name, owner, rows in (
            ("Civil War", None, ((c1, False), (c2, False), (c1, False))),
            ("Civil War", None, ((c2, False), (c3, True), (c4, False))),
            ("Mine", user, ((c3, False), (c4, False))),
            ("Theirs", other, ((c1, False),)),
        ):
            reading_list = ReadingList.objects.create(name=name, user=owner)
            for position, (comic, ignored) in enumerate(rows):
                ReadingListEntry.objects.create(
                    reading_list=reading_list,
                    position=position,
                    comic=comic,
                    ignored=ignored,
                    match_tier=ReadingListMatchTier.MANUAL,
                    manual=True,
                )
        self.client = Client()
        self.client.force_login(user)

    def _grid(
        self, order_by: str, search: str, view_mode: str, client: Client
    ) -> tuple[list, int]:
        settings = {
            "orderBy": order_by,
            "filters": {},
            "search": search,
            "viewMode": view_mode,
        }
        response = client.patch(
            "/api/v4/browse/arcs/settings",
            data=json.dumps(settings),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        response = client.get("/api/v4/browse/arcs/0")
        assert response.status_code == _OK, response.content
        data = response.json()["data"]
        if view_mode == "table":
            return data["rows"], data["count"]
        cards = [
            tuple(row.get(field) for field in _FIELDS) for row in data["collections"]
        ]
        return cards, data["count"]

    def _both_ways(
        self,
        order_by: str,
        *,
        search: str = "",
        view_mode: str = "cover",
        client: Client | None = None,
    ) -> list:
        client = client or self.client
        # Cachalot would answer a repeated query without running it.
        with cachalot_disabled(), CaptureQueriesContext(connection) as new:
            now = self._grid(order_by, search, view_mode, client)
        # Read now: the next request clears the log they are read from.
        new_sql = [query["sql"] for query in new.captured_queries]
        with (
            cachalot_disabled(),
            patch.object(card, "_COLLECTION_BY", _OLD_GROUP_BY),
            patch.object(
                BrowserAnnotateCardView,
                "_one_row_per_list",
                staticmethod(lambda qs: qs),
            ),
        ):
            before = self._grid(order_by, search, view_mode, client)
        assert now == before, (order_by, now, before)
        grouped = [
            sql
            for sql in new_sql
            if "child_count" in sql and 'FROM "codex_readinglist"' in sql
        ]
        assert grouped
        assert any('GROUP BY "codex_readinglist"."id"' in sql for sql in grouped)
        assert not any(sql.startswith("SELECT DISTINCT") for sql in grouped)
        return now[0]

    def test_by_name(self) -> None:
        cards = self._both_ways("sort_name")
        # Two "Civil War" cards and Mine: another user's list is not shown.
        assert [row[1] for row in cards] == ["Civil War", "Civil War", "Mine"]

    def test_in_reading_order(self) -> None:
        assert len(self._both_ways("story_arc_number")) == 3  # noqa: PLR2004

    def test_by_child_count(self) -> None:
        assert len(self._both_ways("child_count")) == 3  # noqa: PLR2004

    def test_under_a_search(self) -> None:
        """Only the lists holding the comic found: the second Civil War, Mine."""
        for comic, name in zip(
            self.comics, ("Alpha", "Beta", "Gamma", "Delta"), strict=True
        ):
            ComicFTS.objects.create(comic=comic, name=name)
        cards = self._both_ways("sort_name", search="delta")
        assert [row[1] for row in cards] == ["Civil War", "Mine"]

    def test_in_table_view(self) -> None:
        assert len(self._both_ways("sort_name", view_mode="table")) == 3  # noqa: PLR2004

    def test_with_a_missing_comic(self) -> None:
        """A comic gone from disk is not counted, either way."""
        missing = self.comics[3]
        missing.missing_since = timezone.now()
        missing.save()
        assert len(self._both_ways("child_count")) == 3  # noqa: PLR2004

    def test_not_signed_in(self) -> None:
        """Only the global lists, the same either way."""
        AdminFlag.objects.filter(key=AdminFlagChoices.NON_USERS.value).update(on=True)
        cards = self._both_ways("sort_name", client=Client())
        assert [row[1] for row in cards] == ["Civil War", "Civil War"]

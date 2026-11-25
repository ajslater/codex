"""
A tag filter on a page of comics needs no DISTINCT (C6).

A tag filter tests membership with an ``IN`` subquery and never joins a
comic's tags inline, so a comic row cannot repeat. The comics query was
still made DISTINCT for any tag filter, over every Comic column. These
tests run each filter both ways, DISTINCT forced as before and as now, on
comics that hold several of the ticked tags, so a join would repeat them:
the same books, in the same order, and the same count.
"""

import json
from typing import Final, override
from unittest.mock import patch

from cachalot.api import cachalot_disabled
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from codex.choices.browser import VUETIFY_NULL_CODE
from codex.models import Character, Genre, Tag
from codex.views.browser.filters.filter import BrowserFilterView
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200


def _distinct_comics(queries: list[str]) -> bool:
    """Whether a page's comics were selected DISTINCT."""
    return any('SELECT DISTINCT "codex_comic"."id"' in sql for sql in queries)


class TagFilterDistinctTests(ReadingListFixture):
    """Four comics; most hold two of the ticked characters and genres."""

    @override
    def setUp(self) -> None:
        super().setUp()
        hero, villain, sidekick = (
            Character.objects.create(name=name) for name in ("Hero", "Villain", "Kid")
        )
        drama, action = (
            Genre.objects.create(name=name) for name in ("Drama", "Action")
        )
        crossover = Tag.objects.create(name="Crossover")
        c1, c2, c3, _c4 = self.comics
        c1.characters.add(hero, villain)
        c2.characters.add(hero, villain, sidekick)
        c3.characters.add(sidekick)
        for comic in (c1, c2, c3):
            comic.genres.add(drama, action)
        c1.tags.add(crossover)
        self.ids = {  # pyright: ignore[reportUninitializedInstanceVariable]
            "hero": hero.pk,
            "villain": villain.pk,
            "drama": drama.pk,
            "action": action.pk,
            "crossover": crossover.pk,
        }
        admin = User.objects.create_user(
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client = Client()
        self.client.force_login(admin)
        self.series = c1.series_id  # pyright: ignore[reportUninitializedInstanceVariable]

    def _page(self, filters: dict) -> tuple[list, int]:
        response = self.client.patch(
            "/api/v4/browse/series/settings",
            data=json.dumps({"filters": filters, "orderBy": "sort_name"}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        response = self.client.get(f"/api/v4/browse/series/{self.series}")
        assert response.status_code == _OK, response.content
        data = response.json()["data"]
        return [book["ids"] for book in data["books"]], data["count"]

    def _both_ways(self, filters: dict) -> list:
        """Return the page, after checking DISTINCT forced gives the same."""
        # Cachalot would answer a repeated query without running it.
        with cachalot_disabled(), CaptureQueriesContext(connection) as plain:
            now = self._page(filters)
        # Read now: the next request clears the log they are read from.
        plain_sql = [query["sql"] for query in plain.captured_queries]
        forced = property(lambda _self: True)
        with (
            cachalot_disabled(),
            patch.object(BrowserFilterView, "comic_filter_uses_m2m", forced),
            CaptureQueriesContext(connection) as distinct,
        ):
            before = self._page(filters)
        assert now == before, (filters, now, before)
        assert plain_sql
        assert not _distinct_comics(plain_sql)
        assert _distinct_comics([query["sql"] for query in distinct.captured_queries])
        return now[0]

    def test_any_of_two_characters(self) -> None:
        ids = self.ids
        books = self._both_ways({"characters": [ids["hero"], ids["villain"]]})
        assert len(books) == 2  # noqa: PLR2004

    def test_every_one_of_two_characters(self) -> None:
        ids = self.ids
        filters = {
            "characters": [ids["hero"], ids["villain"]],
            "match_all": ["characters"],
        }
        assert len(self._both_ways(filters)) == 2  # noqa: PLR2004

    def test_no_character(self) -> None:
        assert len(self._both_ways({"characters": [VUETIFY_NULL_CODE]})) == 1

    def test_two_genres_and_a_tag(self) -> None:
        ids = self.ids
        filters = {"genres": [ids["drama"], ids["action"]], "tags": [ids["crossover"]]}
        assert len(self._both_ways(filters)) == 1

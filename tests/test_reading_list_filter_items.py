"""
The Reading Lists filter over lists that hold whole collections.

Ported from the shelves filter tests when shelves folded into lists. A
list's comics include those its collection items deliver, so filtering by
a list lights up a held publisher's subtree and a held comic's ancestors.
At the lists root the filter shows the lists a list holds. A client still
sending the retired shelves filter gets nothing, and the retired sort keys
are refused.
"""

import json
from typing import Final, override

from cachalot.utils import _get_tables
from django.contrib.auth.models import User
from django.test import Client

from codex.librarian.scribe.readinglists.live import (
    COLLECTION_KIND,
    add_item,
    reconcile_list,
)
from codex.models import Comic, ReadingList, ReadingListSource
from codex.views.readinglists.entries import add_comics
from tests.test_reading_list_live import LiveFixture

_OK: Final = 200
_BAD: Final = 400
_PW: Final = "test-pw-hush-S106"
_SETTINGS: Final = "/api/v4/browse/publishers/settings"


def _data(response):
    body = response.json()
    return body.get("data", body)


class FilterFixture(LiveFixture):
    """Civil War under Marvel, Daredevil beside it; the reader signed in."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.daredevil, self.more = self.make_series("Daredevil")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()
        self.client.force_login(self.reader)

    def browse(self, path: str, filters: dict, top: str = "") -> dict:
        params = {"filters": json.dumps(filters), "search": "", "page": 1}
        if top:
            params["topCollection"] = top
        response = self.client.get(f"/api/v4/browse/{path}", params)
        assert response.status_code == _OK, response.content
        return _data(response)

    def listed(self, filters: dict) -> set[int]:
        """Return the comics the series root shows under the filters."""
        data = self.browse("series", {**filters}, top="series")
        return {row["pk"] for row in data["books"]}

    def comic_pks(self, filters: dict) -> list[int]:
        data = self.browse(f"series/{self.series.pk}", {**filters})
        return [row["pk"] for row in data["books"]]


class ListFilterTests(FilterFixture):
    """A list's comics, by hand or through its items, narrow the browser."""

    def test_a_held_publisher_lights_up_its_subtree(self) -> None:
        """Both series of the publisher show."""
        self.hold(self.mine, "publishers", self.publisher)
        expected = {*self.pks(self.comics), *self.pks(self.more)}
        assert self.listed({"reading_lists": [self.mine.pk]}) == expected

    def test_a_held_comic_keeps_its_ancestors(self) -> None:
        """One Civil War issue by hand: only it shows, under Civil War."""
        add_comics(self.mine, [self.comics[1].pk])
        filters = {"reading_lists": [self.mine.pk]}
        assert self.listed(filters) == {self.comics[1].pk}
        assert self.comic_pks(filters) == [self.comics[1].pk]

    def test_two_lists_match_either(self) -> None:
        """The filter is "in any of these lists"."""
        other = ReadingList.objects.create(name="Other", user=self.reader)
        add_comics(self.mine, [self.comics[0].pk])
        self.hold(other, "series", self.daredevil)
        filters = {"reading_lists": [self.mine.pk, other.pk]}
        assert self.listed(filters) == {self.comics[0].pk, *self.pks(self.more)}

    def test_an_empty_list_matches_nothing(self) -> None:
        """No comics, no rows."""
        assert self.listed({"reading_lists": [self.mine.pk]}) == set()

    def test_another_users_list_matches_nothing(self) -> None:
        """A personal list is no list to anyone else."""
        other = User.objects.create_user(username="other", password=_PW)
        theirs = ReadingList.objects.create(name="Theirs", user=other)
        add_comics(theirs, [self.comics[0].pk])
        assert self.listed({"reading_lists": [theirs.pk]}) == set()

    def test_a_series_shows_once_per_comic(self) -> None:
        """Two lists holding one comic do not repeat it."""
        other = ReadingList.objects.create(name="Other", user=self.reader)
        add_comics(self.mine, [self.comics[0].pk])
        add_comics(other, [self.comics[0].pk])
        filters = {"reading_lists": [self.mine.pk, other.pk]}
        assert self.comic_pks(filters) == [self.comics[0].pk]

    def test_a_cached_browse_follows_a_new_item(self) -> None:
        """Adding a series to the list shows it without a cache clear."""
        add_comics(self.mine, [self.comics[0].pk])
        filters = {"reading_lists": [self.mine.pk]}
        assert self.listed(filters) == {self.comics[0].pk}
        self.hold(self.mine, "series", self.daredevil)
        assert self.listed(filters) == {self.comics[0].pk, *self.pks(self.more)}


class ListsRootTests(FilterFixture):
    """At the lists root, filtering by a list shows the lists it holds."""

    def _nested(self) -> tuple[ReadingList, ReadingList]:
        inner = ReadingList.objects.create(name="Inner", user=self.reader)
        add_comics(inner, [self.comics[0].pk])
        # Shares an issue with the outer list, but is not held by it.
        bystander = ReadingList.objects.create(name="Bystander", user=self.reader)
        add_comics(bystander, [self.comics[0].pk])
        add_item(self.mine, "arcs", inner.pk)
        reconcile_list(self.mine)
        return inner, bystander

    def test_the_lists_root_shows_the_held_lists(self) -> None:
        """Inner only: not the list itself, not one that merely overlaps."""
        inner, _ = self._nested()
        data = self.browse("arcs", {"reading_lists": [self.mine.pk]})
        assert [row["pk"] for row in data["collections"]] == [inner.pk]

    def test_without_the_filter_every_list_shows(self) -> None:
        """The rule only applies while filtering."""
        inner, bystander = self._nested()
        data = self.browse("arcs", {})
        shown = {row["pk"] for row in data["collections"]}
        assert {inner.pk, bystander.pk, self.mine.pk} <= shown


class RetiredTests(FilterFixture):
    """What shelves left behind."""

    def test_a_retired_shelves_filter_matches_nothing(self) -> None:
        """Not the whole library."""
        assert self.listed({}) != set()
        assert self.listed({"shelves": [1]}) == set()

    def test_retired_sort_keys_are_refused(self) -> None:
        """Neither ``favorite`` nor ``shelved`` is a sort key."""
        for key in ("favorite", "shelved"):
            response = self.client.patch(
                _SETTINGS,
                data=json.dumps({"orderBy": key}),
                content_type="application/json",
            )
            assert response.status_code == _BAD, key


def test_cachalot_sees_a_group_by_query_in_subquery() -> None:
    """
    The query shape itself: an ``__in`` subquery's table is a dependency.

    ``Comic.objects`` is a ``GroupByManager``, so both querysets build
    ``GroupByQuery`` objects, the subclass cachalot's identity test missed.
    Kept from the shelves cache tests when shelves folded into lists.
    """
    targets = ReadingListSource.objects.filter(
        kind=COLLECTION_KIND, collection="publishers"
    ).values("target_id")
    qs = Comic.objects.filter(publisher_id__in=targets)
    assert "codex_readinglistsource" in _get_tables("default", qs.query)

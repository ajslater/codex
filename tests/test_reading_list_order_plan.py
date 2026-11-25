"""
A list's comics find their first position through the comic's index (B16).

B16 ordered a list's comics by a per-comic subquery, ``ORDER BY position
LIMIT 1``. SQLite served that order from the list's position index, so
for every comic it walked the list's entries in order until it met that
comic: a 5,000-entry list's page took a second. The first (or last)
position is an aggregate now, which SQLite answers from the comic's own
index.

The guard reads the plan SQLite picks for the page's comics query, on the
test database, which has no statistics as a fresh install has none: a
change that brings the walk back shows as the position index there. The
plan is the defect itself, so a timing would only stand in for it, and
flakily.
"""

import json
from typing import Final

from cachalot.api import cachalot_disabled
from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests.test_reading_list_order import ReadingOrderFixture

_OK: Final = 200
_READING_ORDER: Final = "story_arc_number"


class ListOrderPlanTests(ReadingOrderFixture):
    """A list's own page in Reading Order, both directions."""

    def _plan(self, *, reverse: bool) -> list[str]:
        """Return the plan lines of the page's entry subqueries."""
        reading_list = self.make_list("Event", self.comics[::-1])
        response = self.client.patch(
            "/api/v4/browse/arcs/settings",
            data=json.dumps({"orderBy": _READING_ORDER, "orderReverse": reverse}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        with cachalot_disabled(), CaptureQueriesContext(connection) as queries:
            response = self.client.get(f"/api/v4/browse/arcs/{reading_list.pk}")
        assert response.status_code == _OK, response.content
        assert [book["ids"][0] for book in response.json()["data"]["books"]] == [
            comic.pk for comic in (self.comics if reverse else self.comics[::-1])
        ]
        (sql,) = (
            query["sql"]
            for query in queries.captured_queries
            if '"codex_comic"."id"' in query["sql"][:40]
            and 'FROM "codex_readinglistentry" "U0"' in query["sql"]
            and "LIMIT" in query["sql"]
        )
        with connection.cursor() as cursor:
            cursor.execute(f"EXPLAIN QUERY PLAN {sql}")
            return [row[-1] for row in cursor.fetchall() if "U0" in row[-1]]

    def test_first_position_uses_the_comic_index(self) -> None:
        plan = self._plan(reverse=False)
        assert plan
        assert all("readinglistentry_comic_list" in line for line in plan), plan

    def test_last_position_uses_the_comic_index(self) -> None:
        plan = self._plan(reverse=True)
        assert plan
        assert all("readinglistentry_comic_list" in line for line in plan), plan

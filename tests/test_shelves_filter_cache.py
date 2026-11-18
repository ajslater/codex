"""
A shelf-filtered browse sees shelf changes without a cache clear.

cachalot finds a ``WHERE x__in=<subquery>``'s inner table only when the
subquery is a stock ``Query``, by identity, and every codex query is a
``GroupByQuery``. So the shelves filter was cached with no dependency on
``codex_shelfitem``: add an item to a collection the shelf already holds
and the browse runs byte-identical SQL, which cachalot answered with the
old rows and the old count.

The cache must not be cleared between the requests, or the bug hides.
"""

import json
from typing import TYPE_CHECKING, override

from tests.shelf_fixtures import (
    HTTP_OK,
    SETTINGS_URL,
    ShelfTestCase,
    items_url,
    post_json,
    v4,
)

if TYPE_CHECKING:
    from codex.models import Shelf

_PUBLISHERS_URL = "/api/v4/browse/publishers?page=1"


class ShelfFilterCacheTestCase(ShelfTestCase):
    """Rows and count follow the shelf, in cover and table view."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.shelf: Shelf = self._shelf()  # pyright: ignore[reportUninitializedInstanceVariable]
        self._put(self.shelf, "publishers", self.p1.pk)
        self._patch_settings({"filters": {"shelves": [self.shelf.pk]}})

    def _patch_settings(self, payload: dict) -> None:
        response = post_json(self.client, "patch", SETTINGS_URL, payload)
        assert response.status_code == HTTP_OK, response.content

    def _change_items(self, action: str, publisher_pk: int) -> None:
        response = self.client.patch(
            items_url(self.shelf.pk),
            data=json.dumps({action: {"publishers": [publisher_pk]}}),
            content_type="application/json",
        )
        assert response.status_code == HTTP_OK, response.content

    def _browse(self) -> tuple[list[int], int]:
        response = self.client.get(_PUBLISHERS_URL)
        assert response.status_code == HTTP_OK, response.content
        data = v4(response)
        rows = data.get("rows") or data.get("collections") or []
        pks = sorted(
            pk
            for row in rows
            for pk in (row.get("ids") or [row.get("pk")])
            if pk is not None
        )
        return pks, data["count"]

    def _assert_follows_the_shelf(self) -> None:
        assert self._browse() == ([self.p1.pk], 1)

        self._change_items("add", self.p2.pk)
        assert self._browse() == (sorted([self.p1.pk, self.p2.pk]), 2)

        self._change_items("remove", self.p1.pk)
        assert self._browse() == ([self.p2.pk], 1)

    def test_cover_view_follows_the_shelf(self) -> None:
        self._assert_follows_the_shelf()

    def test_table_view_follows_the_shelf(self) -> None:
        self._patch_settings({"viewMode": "table"})
        self._assert_follows_the_shelf()


def test_cachalot_sees_a_group_by_query_in_subquery() -> None:
    """
    The query shape itself: an ``__in`` subquery's table is a dependency.

    ``Comic.objects`` is a ``GroupByManager``, so both querysets build
    ``GroupByQuery`` objects, the subclass cachalot's identity test missed.
    """
    from cachalot.utils import _get_tables

    from codex.models import Comic, ShelfItem

    targets = ShelfItem.objects.filter(collection="publishers").values("target_id")
    qs = Comic.objects.filter(publisher_id__in=targets)
    assert "codex_shelfitem" in _get_tables("default", qs.query)

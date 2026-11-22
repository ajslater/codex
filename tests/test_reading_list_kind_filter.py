"""
The Reading List Kind filter: Mine, Curated, From Tags.

On the grid of lists it narrows the lists. Inside one list it does
nothing: the list's page, mtime, metadata, download and missing issues are
the same whatever kind is picked.
"""

import json
from pathlib import Path
from typing import Final

from django.core.cache import cache

from codex.models import ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from tests.test_reading_list_manage import ManageFixture

_OK: Final = 200


class OneListIgnoresTheGridFilters(ManageFixture):
    """A list opened with a kind picked that it is not, or a list filter."""

    def _browse_grid(self, filters: dict) -> None:
        """Browse the grid of lists, which saves the filters to settings."""
        params = {"filters": json.dumps(filters), "search": ""}
        response = self.client.get("/api/v4/browse/arcs/0", params)
        assert response.status_code == _OK, response.content

    def _page(self) -> dict:
        cache.clear()
        params = {"order_by": "story_arc_number", "order_reverse": "false"}
        response = self.client.get(f"/api/v4/browse/arcs/{self.mine.pk}", params)
        assert response.status_code == _OK, response.content
        return response.json()["data"]

    def _probe_mtime(self) -> int:
        cache.clear()
        collections = json.dumps([{"collection": "arcs", "pks": str(self.mine.pk)}])
        response = self.client.get("/api/v4/mtime", {"collections": collections})
        assert response.status_code == _OK, response.content
        return response.json()["data"]["maxMtime"]

    def _assert_the_list_is_whole(self) -> None:
        cache.clear()
        page = self._page()
        assert page["mtime"], page
        assert {book["pk"] for book in page["books"]} == {
            comic.pk for comic in self.comics[2:]
        }
        assert self._probe_mtime()
        cache.clear()
        metadata = self.client.get(f"/api/v4/browse/arcs/{self.mine.pk}/metadata")
        assert metadata.status_code == _OK, metadata.content
        for comic in self.comics:
            Path(comic.path).write_bytes(b"PK")
        cache.clear()
        download = self.client.get(
            f"/api/v4/browse/arcs/{self.mine.pk}/download/Mine.zip"
        )
        assert download.status_code == _OK, download.content

    def test_another_kind_picked(self) -> None:
        """From Tags picked: the viewer's own list still opens whole."""
        self._browse_grid({"readingListKind": "tags"})
        self._assert_the_list_is_whole()

    def test_another_list_filtered(self) -> None:
        """
        Filtered by a list that does not hold it: it still opens.

        On the grid the Reading Lists filter shows the lists a list holds.
        Inside one list it narrows the comics as any filter does, so the
        comic both lists share stays.
        """
        self._browse_grid({"readingLists": [self.handmade.pk]})
        cache.clear()
        metadata = self.client.get(f"/api/v4/browse/arcs/{self.mine.pk}/metadata")
        assert metadata.status_code == _OK, metadata.content
        assert self._probe_mtime()
        page = self._page()
        assert page["mtime"], page
        assert [book["pk"] for book in page["books"]] == [self.comics[2].pk]

    def test_missing_issues_show_with_a_kind_picked(self) -> None:
        """The kind does not count as narrowing the list's comics."""
        ReadingListEntry.objects.create(
            reading_list=self.mine,
            position=2,
            comic=None,
            series_name="Tie-In",
            issue="1",
            match_tier=ReadingListMatchTier.NONE,
        )
        self._browse_grid({"readingListKind": "tags"})
        page = self._page()
        missing = [entry["seriesName"] for entry in page.get("missingEntries") or ()]
        assert missing == ["Tie-In"], page

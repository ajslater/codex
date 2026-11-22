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

from codex.librarian.scribe.readinglists.live import add_item
from codex.models import ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from codex.models.settings import SettingsBrowserFilters
from tests.test_reading_list_manage import ManageFixture

_OK: Final = 200
_BAD_REQUEST: Final = 400


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
        self._browse_grid({"readingListKind": ["tags"]})
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
        self._browse_grid({"readingListKind": ["tags"]})
        page = self._page()
        missing = [entry["seriesName"] for entry in page.get("missingEntries") or ()]
        assert missing == ["Tie-In"], page


class GridKindTests(ManageFixture):
    """On the grid of lists the kind narrows the lists; several kinds OR."""

    def test_nothing_picked_is_every_list(self) -> None:
        """Cleared means every list the viewer sees."""
        assert self._root([]) == {"From Tags", "Imported", "Hand Made", "Mine"}

    def test_curated_is_not_from_tags_only(self) -> None:
        """Hand-made lists are curated too, and so are the viewer's own."""
        assert self._root(["curated"]) == {"Imported", "Hand Made", "Mine"}

    def test_from_tags(self) -> None:
        """Lists whose only source is their tags."""
        assert self._root(["tags"]) == {"From Tags"}

    def test_mine(self) -> None:
        """The viewer's own lists."""
        assert self._root(["mine"]) == {"Mine"}

    def test_two_kinds_add_up(self) -> None:
        """The API takes several kinds and shows a list of any of them."""
        assert self._root(["mine", "tags"]) == {"Mine", "From Tags"}

    def test_anonymous_mine_is_nothing(self) -> None:
        """A session owns no lists."""
        self.client.logout()
        assert self._root(["mine"]) == set()

    def test_an_unknown_kind_is_refused(self) -> None:
        """Only the three kinds."""
        assert self._root_response(["everything"]).status_code == _BAD_REQUEST

    def test_a_bare_string_is_refused(self) -> None:
        """The kind is a list, like every other filter."""
        assert self._root_response("mine").status_code == _BAD_REQUEST

    def test_the_pick_is_saved_and_loaded(self) -> None:
        """A browse saves the kind; the next one without filters uses it."""
        self._root(["tags"])
        filters = SettingsBrowserFilters.objects.get(browser__user=self.user)
        assert filters.reading_list_kind == ["tags"]
        response = self.client.get("/api/v4/browse/arcs/0")
        assert response.status_code == _OK, response.content
        names = {row["name"] for row in response.json()["data"]["collections"]}
        assert names == {"From Tags"}


class GridKindChoicesTests(ManageFixture):
    """The filter menu offers the kinds with lists behind them."""

    def _available(self, filters: dict | None = None) -> bool:
        params = {"filters": json.dumps(filters or {}), "search": ""}
        response = self.client.get("/api/v4/browse/arcs/0/choices", params)
        assert response.status_code == _OK, response.content
        return response.json()["data"]["readingListKind"]

    def _rows(self, filters: dict | None = None) -> list[tuple[str, str]]:
        params = {"filters": json.dumps(filters or {}), "search": ""}
        response = self.client.get(
            "/api/v4/browse/arcs/0/choices/readingListKind", params
        )
        assert response.status_code == _OK, response.content
        return [(row["pk"], row["name"]) for row in response.json()["data"]["choices"]]

    def test_every_kind_in_menu_order(self) -> None:
        """Mine, Curated, From Tags: a fixed order, not by name."""
        assert self._available()
        assert self._rows() == [
            ("mine", "Mine"),
            ("curated", "Curated"),
            ("tags", "From Tags"),
        ]

    def test_every_kind_still_offered_with_one_picked(self) -> None:
        """Switching is one step: the picked kind does not narrow its own menu."""
        picked = {"readingListKind": ["tags"]}
        assert self._available(picked)
        assert [pk for pk, _ in self._rows(picked)] == ["mine", "curated", "tags"]

    def test_a_kind_with_no_lists_is_not_offered(self) -> None:
        """No list of the viewer's own: no Mine."""
        self.mine.delete()
        assert [pk for pk, _ in self._rows()] == ["curated", "tags"]

    def test_anonymous_never_sees_mine(self) -> None:
        """A session owns no lists."""
        self.client.logout()
        assert [pk for pk, _ in self._rows()] == ["curated", "tags"]

    def test_hidden_with_one_kind(self) -> None:
        """Only lists from tags: nothing to choose between."""
        self.mine.delete()
        self.imported.delete()
        self.handmade.delete()
        assert not self._available()

    def test_shown_with_one_kind_when_it_is_picked(self) -> None:
        """A picked kind stays in the menu, so it can be cleared."""
        self.mine.delete()
        self.imported.delete()
        self.handmade.delete()
        assert self._available({"readingListKind": ["tags"]})

    def test_the_other_filters_narrow_the_kinds(self) -> None:
        """Filtered by a list that holds only tag lists: Curated goes."""
        holder = self._list("Holder", (), user=self.user)
        add_item(holder, "arcs", self.tags_list.pk)
        rows = self._rows({"readingLists": [holder.pk]})
        assert [pk for pk, _ in rows] == ["tags"]

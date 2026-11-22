"""
The Reading List Kind outside the grid of lists.

In every other view it narrows to comics on a list of that kind that the
viewer may see: Mine in the Series view is every comic on one of the
viewer's own lists. Inside one list it does nothing.
"""

import json
from typing import Final, override

from cachalot.utils import _get_tables

from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.models import Comic, ReadingList, ReadingListSource
from codex.models.readinglist import ReadingListSourceKind
from codex.views.browser.filters.reading_lists import listed_comics
from codex.views.readinglists.entries import add_comics
from tests.test_reading_list_filter_items import FilterFixture

_OK: Final = 200
_MINE: Final = {"reading_list_kind": ["mine"]}


class KindFixture(FilterFixture):
    """The reader's list, a global hand-made list, and a list from tags."""

    @override
    def setUp(self) -> None:
        super().setUp()
        c1, c2, c3, _ = self.comics
        add_comics(self.mine, [c1.pk])
        self.handmade = ReadingList.objects.create(name="Hand Made")  # pyright: ignore[reportUninitializedInstanceVariable]
        add_comics(self.handmade, [c2.pk])
        self.tag(c3, "Tagged", 1)
        sync_tag_lists()
        self.tagged = ReadingList.objects.get(name="Tagged")  # pyright: ignore[reportUninitializedInstanceVariable]

    def books(self, path: str, filters: dict) -> list[int]:
        return [row["pk"] for row in self.browse(path, filters)["books"]]

    def reader_next(self, comic: Comic, arc: dict) -> int | None:
        response = self.client.get(
            f"/api/v4/reader/comics/{comic.pk}", {"arc": json.dumps(arc)}
        )
        assert response.status_code == _OK, response.content
        following = response.json()["data"]["books"].get("next")
        return following["pk"] if following else None


class KindInEveryViewTests(KindFixture):
    """Comics on a list of the picked kinds."""

    def test_mine_in_the_series_view(self) -> None:
        """Only the comic on the viewer's own list."""
        assert self.listed(_MINE) == {self.comics[0].pk}

    def test_curated_includes_the_viewers_own(self) -> None:
        """Hand-made global lists and the viewer's own; not the tag list."""
        curated = {"reading_list_kind": ["curated"]}
        assert self.listed(curated) == {self.comics[0].pk, self.comics[1].pk}

    def test_from_tags(self) -> None:
        """Only the comic on the list from tags."""
        assert self.listed({"reading_list_kind": ["tags"]}) == {self.comics[2].pk}

    def test_two_kinds_add_up(self) -> None:
        """Mine or From Tags."""
        filters = {"reading_list_kind": ["mine", "tags"]}
        assert self.listed(filters) == {self.comics[0].pk, self.comics[2].pk}

    def test_mine_in_a_folder(self) -> None:
        """A folder's comics narrow the same way."""
        books = self.books(f"folders/{self.folder.pk}", _MINE)
        assert books == [self.comics[0].pk]

    def test_another_users_list_is_not_theirs(self) -> None:
        """Mine is the viewer's own lists, not anyone's personal list."""
        self.client.logout()
        assert self.listed(_MINE) == set()

    def test_a_comic_on_two_lists_counts_once(self) -> None:
        """An ``IN`` subquery, not a join: the series' sums are per comic."""
        other = ReadingList.objects.create(name="Other", user=self.reader)
        add_comics(other, [self.comics[0].pk])
        response = self.client.get(
            f"/api/v4/browse/series/{self.series.pk}/metadata",
            {"filters": json.dumps(_MINE), "search": ""},
        )
        assert response.status_code == _OK, response.content
        data = response.json()["data"]
        assert (data["childCount"], data["pageCount"]) == (1, 10), data


class KindInsideOneListTests(KindFixture):
    """A list opens whole whatever kind is picked."""

    def test_its_comics(self) -> None:
        """The hand-made list is not the viewer's, and still shows its comic."""
        assert self.books(f"arcs/{self.handmade.pk}", _MINE) == [self.comics[1].pk]

    def test_its_page_mtime(self) -> None:
        """The page's mtime is the list's, not the epoch."""
        assert self.browse(f"arcs/{self.handmade.pk}", _MINE)["mtime"]

    def test_the_reader_through_a_list(self) -> None:
        """Reading through a list ignores the kind."""
        add_comics(self.handmade, [self.comics[3].pk])
        self.browse(f"arcs/{self.handmade.pk}", _MINE)
        arc = {"collection": "arcs", "ids": [self.handmade.pk]}
        assert self.reader_next(self.comics[1], arc) == self.comics[3].pk

    def test_the_reader_through_a_series(self) -> None:
        """Reading through anything else, next and previous follow the kind."""
        add_comics(self.mine, [self.comics[3].pk])
        self.browse("series", _MINE, top="series")
        arc = {"collection": "series", "ids": [self.series.pk]}
        assert self.reader_next(self.comics[0], arc) == self.comics[3].pk

    def test_not_offered_inside_one_list(self) -> None:
        """Nothing to narrow there."""
        response = self.client.get(
            f"/api/v4/browse/arcs/{self.handmade.pk}/choices",
            {"filters": json.dumps({}), "search": ""},
        )
        assert response.status_code == _OK, response.content
        assert not response.json()["data"]["readingListKind"]


class KindChoicesInViewsTests(KindFixture):
    """Off the grid, a kind is offered when comics here are on lists of it."""

    def _rows(self, path: str, filters: dict) -> list[str]:
        response = self.client.get(
            f"/api/v4/browse/{path}/choices/readingListKind",
            {"filters": json.dumps(filters), "search": ""},
        )
        assert response.status_code == _OK, response.content
        return [row["pk"] for row in response.json()["data"]["choices"]]

    def test_every_kind_in_the_series_view(self) -> None:
        """Mine, Curated, From Tags, with Mine picked too."""
        assert self._rows("series/0", {}) == ["mine", "curated", "tags"]
        assert self._rows("series/0", _MINE) == ["mine", "curated", "tags"]

    def test_the_other_filters_narrow_the_kinds(self) -> None:
        """Filtered to the tag list's comic: only From Tags, and none else."""
        filters = {"reading_lists": [self.tagged.pk]}
        assert self._rows("series/0", filters) == ["tags"]


class KindCacheTests(KindFixture):
    """A cached Series view follows the lists, entries and sources."""

    def test_a_new_entry_shows(self) -> None:
        """A comic added to the viewer's list joins Mine."""
        assert self.listed(_MINE) == {self.comics[0].pk}
        add_comics(self.mine, [self.comics[3].pk])
        assert self.listed(_MINE) == {self.comics[0].pk, self.comics[3].pk}

    def test_a_list_given_to_the_viewer_shows(self) -> None:
        """A list that becomes the viewer's joins Mine."""
        assert self.listed(_MINE) == {self.comics[0].pk}
        ReadingList.objects.filter(pk=self.handmade.pk).update(user=self.reader)
        assert self.listed(_MINE) == {self.comics[0].pk, self.comics[1].pk}

    def test_a_new_source_moves_a_list_out_of_from_tags(self) -> None:
        """An upload on the tag list makes it curated."""
        tags = {"reading_list_kind": ["tags"]}
        assert self.listed(tags) == {self.comics[2].pk}
        ReadingListSource.objects.create(
            reading_list=self.tagged, kind=ReadingListSourceKind.UPLOAD, ref="x.cbl"
        )
        assert self.listed(tags) == set()

    def test_the_query_names_the_sources_table(self) -> None:
        """Cachalot invalidates the browse on a source change."""
        for kind in ("curated", "tags"):
            listed = listed_comics(self.reader, kinds=[kind])
            query = Comic.objects.filter(pk__in=listed).query
            assert "codex_readinglistsource" in _get_tables("default", query), kind

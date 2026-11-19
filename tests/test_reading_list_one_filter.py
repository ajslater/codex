"""
Story arcs and reading lists are one filter: Reading Lists.

There is no Story Arcs filter any more. Reading Lists offers every list the
viewer may see, a saved view keeps only lists its owner may see, and Reading
Order under the filter sorts by place in the chosen list.
"""

import json
from typing import Final

from codex.choices.readinglists import list_type_label
from codex.models import ReadingListEntry, Series
from codex.models.settings import (
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserShow,
)
from codex.user_data.restore import (
    RestoreReport,
    _rename_sort_key,
    _restore_one_filter,
)
from codex.user_data.serializers import serialize_settings_filters
from codex.views.auth import ComicACL
from codex.views.browser.intersections import (
    compute_collection_intersections,
    m2m_intersection_sort_expr,
)
from codex.views.browser.filters.search.parse import _preparse_search_query_cached
from codex.views.browser.saved_settings import _validate_filter_pks
from tests.test_reading_list_filter import _SHOW_ALL, _ListsFixture

_OK: Final = 200


class OneFilterTests(_ListsFixture):
    """The Story Arcs filter is gone; Reading Lists does its work."""

    def _choices(self) -> dict:
        params = {"filters": json.dumps({}), "search": ""}
        response = self.client.get("/api/v4/browse/series/0/choices", params)
        assert response.status_code == _OK, response.content
        return response.json()["data"]

    def test_no_story_arcs_filter_is_offered(self) -> None:
        """The filter menu offers Reading Lists and no Story Arcs."""
        self.tag(self.comics[0], "Civil War", 1)
        choices = self._choices()
        assert "storyArcs" not in choices
        assert choices["readingLists"] is True

    def test_a_saved_view_keeps_only_visible_lists(self) -> None:
        """Another user's list pk is stripped from a saved filter."""
        filters = {"reading_lists": [self.shared.pk, self.secret.pk, None]}
        warnings = _validate_filter_pks(filters, user=self.other)
        assert warnings == ["reading_lists"]
        assert filters["reading_lists"] == [self.shared.pk, None]

    def test_the_owner_keeps_their_list(self) -> None:
        """A list's owner may save a filter on it."""
        filters = {"reading_lists": [self.secret.pk]}
        assert _validate_filter_pks(filters, user=self.owner) == []
        assert filters["reading_lists"] == [self.secret.pk]


class FilterReadingOrderTests(_ListsFixture):
    """Reading Order under the Reading Lists filter is the list's own order."""

    def _books(self, *, order_reverse: bool = False) -> list[int]:
        params = {
            "filters": json.dumps({"readingLists": [self.shared.pk]}),
            "search": "",
            "show": json.dumps(_SHOW_ALL),
            "view_mode": "cover",
            "order_by": "story_arc_number",
            "order_reverse": json.dumps(order_reverse),
        }
        volume_pk = self.comics[0].volume_id
        response = self.client.get(f"/api/v4/browse/volumes/{volume_pk}", params)
        assert response.status_code == _OK, response.content
        return [book["pk"] for book in response.json()["data"]["books"]]

    def test_list_order_not_issue_order(self) -> None:
        """A list that reads #2 before #1 sorts that way under the filter."""
        c1, c2 = self.comics[:2]
        ReadingListEntry.objects.filter(reading_list=self.shared, comic=c1).update(
            position=1
        )
        ReadingListEntry.objects.filter(reading_list=self.shared, comic=c2).update(
            position=0
        )
        assert self._books() == [c2.pk, c1.pk]
        assert self._books(order_reverse=True) == [c1.pk, c2.pk]


class ReadingListsColumnTests(_ListsFixture):
    """The Reading Lists column of a collection row names its shared lists."""

    def test_a_series_row_names_lists_every_comic_is_in(self) -> None:
        """All four comics are in Everything; Shared holds only two."""
        everything = self._list("Everything", self.comics)
        theirs = self._list("Theirs Too", self.comics, user=self.owner)
        assert theirs.pk
        series = self.comics[0].series
        acl = ComicACL.for_user(self.other)
        isect = compute_collection_intersections(
            Series.objects.filter(pk=series.pk), ("reading_lists",), acl
        )
        assert isect[series.pk]["reading_lists"] == [everything.name]

    def test_sorting_series_rows_by_reading_lists_runs(self) -> None:
        """The raw-SQL sort key runs and sees only the viewer's lists."""
        self._list("Everything", self.comics)
        series = self.comics[0].series
        acl = ComicACL.for_user(self.other)
        expr = m2m_intersection_sort_expr(Series, "reading_lists", acl)
        assert expr is not None
        value = (
            Series.objects.filter(pk=series.pk)
            .annotate(key=expr)
            .values_list("key", flat=True)
            .get()
        )
        assert value == "Everything"


class OldBackupTests(_ListsFixture):
    """A backup from before the fold restores as reading lists."""

    def test_a_story_arc_filter_restores_as_its_list(self) -> None:
        """An old row's arc names become the global lists of those names."""
        filters = SettingsBrowserFilters.objects.create(
            browser=SettingsBrowser.objects.create(
                user=self.other, show=SettingsBrowserShow.objects.get_or_create()[0]
            )
        )
        row = {"bookmark": "", "story_arcs": json.dumps(["Shared", "Gone"])}
        _restore_one_filter(row, filters.browser, RestoreReport())
        filters.refresh_from_db()
        assert filters.reading_lists == [self.shared.pk]

    def test_an_old_sort_key_restores_renamed(self) -> None:
        """The Story Arcs sort and column restore as Reading Lists."""
        assert _rename_sort_key("story_arcs") == "reading_lists"

    def test_a_dump_writes_no_story_arcs(self) -> None:
        """New dumps stop writing the retired column."""
        filters = SettingsBrowserFilters.objects.create(
            browser=SettingsBrowser.objects.create(
                user=self.other, show=SettingsBrowserShow.objects.get_or_create()[0]
            ),
            reading_lists=[self.shared.pk],
        )
        dumped = serialize_settings_filters(filters)
        assert dumped is not None
        assert "story_arcs" not in dumped[2]


class SearchFieldTests(_ListsFixture):
    """``reading_lists:`` searches; the story-arc names stay its aliases."""

    def test_the_field_and_its_old_names_search_the_arc_column(self) -> None:
        """Every spelling reaches the arc names in the search index."""
        for field in ("reading_lists", "reading-lists", "story_arcs", "arc", "arcs"):
            _, fts_text, _ = _preparse_search_query_cached(f"{field}:civil", False)
            assert fts_text == "story_arcs:civil", field

    def test_a_prefix_search_stays_in_the_index(self) -> None:
        """A trailing wildcard is an index prefix query on the arc names."""
        _, fts_text, _ = _preparse_search_query_cached("reading_lists:Civ*", False)
        assert fts_text == "story_arcs:Civ*"


class ListTypeLabelTests(_ListsFixture):
    """A list shows its type as people read it."""

    def test_lists_from_tags_are_story_arcs(self) -> None:
        """comicbox's ``story`` is a Story Arc; unknown types show as given."""
        assert list_type_label("story") == "Story Arc"
        assert list_type_label("event") == "Event"
        assert list_type_label("tie-in-order") == "Tie In Order"

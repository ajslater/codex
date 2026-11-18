"""Tests for the shelves a browser row or metadata selection is listed on."""

from types import SimpleNamespace
from typing import Final, override

from django.contrib.auth.models import AnonymousUser, User
from django.db.models import JSONField, Value
from django.test import SimpleTestCase
from django.utils import timezone

from codex.models import Comic, Folder, Library, Series, StoryArc, Volume
from codex.models.named import StoryArcNumber
from codex.models.shelf import SHELF_MODEL_COLLECTIONS
from codex.serializers.browser.page import BrowserPageSerializer
from codex.views.auth import ComicACL
from codex.views.browser.shelf_membership import (
    SHELF_COMIC_COLLECTIONS,
    page_row_shelves,
    selection_shelves,
)
from tests.shelf_fixtures import (
    HTTP_OK,
    SETTINGS_URL,
    TEST_PASSWORD,
    TMP_DIR,
    ShelfTestCase,
    items_url,
    post_json,
    v4,
)

_SHOW_ALL: Final = {
    "publishers": True,
    "imprints": True,
    "series": True,
    "volumes": True,
}


class ShelfMembershipTestCase(ShelfTestCase):
    """Effective membership: direct, or through any parent of the comic."""

    @override
    def setUp(self) -> None:
        super().setUp()
        # A second issue under the first chain's series, so the series row
        # has two comics to intersect over.
        path = TMP_DIR / "c1b.cbz"
        path.touch()
        self.c1b = Comic.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=self.library,
            path=path,
            issue_number=3,
            name="C1b",
            publisher=self.p1,
            imprint=self.i1,
            series=self.s1,
            volume=self.v1,
            size=1,
        )

    def _acl(self, user=None) -> ComicACL:
        return ComicACL.for_user(user or self.user)

    def _book_shelves(self, *comics: Comic, user=None) -> dict[int, list[int]]:
        book_qs = Comic.objects.filter(pk__in=[comic.pk for comic in comics])
        user = user or self.user
        return page_row_shelves(user, self._acl(user), None, book_qs)["books"]

    def _series_shelves(self, *series: Series) -> dict[int, list[int]]:
        qs = Series.objects.filter(pk__in=[s.pk for s in series])
        return page_row_shelves(self.user, self._acl(), qs, None)["collections"]

    def test_every_shelvable_collection_has_a_comic_clause(self):
        """A new shelvable collection must say how it reaches a comic."""
        codes = {code.value for code in SHELF_MODEL_COLLECTIONS.values()}
        assert codes == SHELF_COMIC_COLLECTIONS

    def test_comic_lists_direct_and_inherited_shelves(self):
        """A comic is on a shelf itself or through its publisher … volume."""
        direct = self._shelf("Direct")
        self._put(direct, "comics", self.c1.pk)
        parents = {
            "publishers": self.p1.pk,
            "imprints": self.i1.pk,
            "series": self.s1.pk,
            "volumes": self.v1.pk,
        }
        inherited = {}
        for collection, target_id in parents.items():
            shelf = self._shelf(f"Via {collection}")
            self._put(shelf, collection, target_id)
            inherited[collection] = shelf.pk
        unrelated = self._shelf("Other chain")
        self._put(unrelated, "series", self.s2.pk)

        shelves = self._book_shelves(self.c1)[self.c1.pk]
        assert set(shelves) == {direct.pk, *inherited.values()}

    def test_shelves_come_back_in_name_order(self):
        """The pk list follows shelf names, as the shelf menu lists them."""
        beta = self._shelf("Beta")
        alpha = self._shelf("Alpha")
        self._put(beta, "comics", self.c1.pk)
        self._put(alpha, "comics", self.c1.pk)
        assert self._book_shelves(self.c1)[self.c1.pk] == [alpha.pk, beta.pk]

    def test_comic_inherits_from_an_ancestor_folder(self):
        """A shelved folder reaches every comic below it, however deep."""
        library_dir = TMP_DIR / "ftree"
        top_dir = library_dir / "top"
        leaf_dir = top_dir / "leaf"
        leaf_dir.mkdir(parents=True, exist_ok=True)
        library = Library.objects.create(path=str(library_dir))
        top = Folder.objects.create(library=library, path=str(top_dir))
        leaf = Folder.objects.create(
            library=library, parent_folder=top, path=str(leaf_dir)
        )
        self.c1.folders.set([top, leaf])
        shelf = self._shelf()
        self._put(shelf, "folders", top.pk)

        assert self._book_shelves(self.c1, self.c2) == {
            self.c1.pk: [shelf.pk],
            self.c2.pk: [],
        }

    def test_comic_inherits_from_a_story_arc(self):
        """A shelved arc reaches every comic in it."""
        arc = StoryArc.objects.create(name="Arc")
        self.c1.story_arc_numbers.add(
            StoryArcNumber.objects.create(story_arc=arc, number=1)
        )
        shelf = self._shelf()
        self._put(shelf, "arcs", arc.pk)

        assert self._book_shelves(self.c1, self.c2) == {
            self.c1.pk: [shelf.pk],
            self.c2.pk: [],
        }

    def test_collection_row_lists_only_shelves_every_comic_shares(self):
        """A series shows a shelf only when all its comics are on it."""
        both = self._shelf("Both")
        self._put(both, "comics", self.c1.pk)
        self._put(both, "comics", self.c1b.pk)
        one = self._shelf("One")
        self._put(one, "comics", self.c1.pk)

        assert self._series_shelves(self.s1, self.s2) == {
            self.s1.pk: [both.pk],
            self.s2.pk: [],
        }

    def test_collection_row_on_a_shelf_lists_it(self):
        """A shelved row is shared by all its comics, so it lists the shelf."""
        shelf = self._shelf()
        self._put(shelf, "series", self.s1.pk)
        assert self._series_shelves(self.s1)[self.s1.pk] == [shelf.pk]

    def test_collection_row_counts_only_live_comics(self):
        """A comic kept only for its bookmarks doesn't blank the row."""
        shelf = self._shelf()
        self._put(shelf, "comics", self.c1.pk)
        Comic.objects.filter(pk=self.c1b.pk).update(missing_since=timezone.now())
        assert self._series_shelves(self.s1)[self.s1.pk] == [shelf.pk]

    def test_merged_row_needs_every_merged_pk(self):
        """A row standing for several pks shares a shelf only across all of them."""
        twin = Volume.objects.create(
            name="1", publisher=self.p2, imprint=self.i2, series=self.s2
        )
        Comic.objects.filter(pk=self.c2.pk).update(volume=twin)
        only_first = self._shelf("First")
        self._put(only_first, "volumes", self.v1.pk)
        both = self._shelf("Both")
        self._put(both, "volumes", self.v1.pk)
        self._put(both, "volumes", twin.pk)

        # Volumes group by name, so ``v1`` and its same-named ``twin`` browse
        # as one row whose ``ids`` holds both pks.
        qs = Volume.objects.filter(pk=self.v1.pk).annotate(
            ids=Value([self.v1.pk, twin.pk], output_field=JSONField())
        )
        rows = page_row_shelves(self.user, self._acl(), qs, None)["collections"]
        assert rows == {self.v1.pk: [both.pk]}

    def test_other_users_shelves_never_show(self):
        """Only the requesting user's shelves are reported."""
        other = User.objects.create_user(username="other", password=TEST_PASSWORD)
        self._put(self._shelf("Theirs", user=other), "comics", self.c1.pk)
        mine = self._shelf("Mine")
        self._put(mine, "comics", self.c2.pk)
        assert self._book_shelves(self.c1, self.c2) == {
            self.c1.pk: [],
            self.c2.pk: [mine.pk],
        }

    def test_anonymous_and_shelfless_users_short_circuit(self):
        """No shelves, no queries over comics, empty maps."""
        self._put(self._shelf(), "comics", self.c1.pk)
        book_qs = Comic.objects.filter(pk=self.c1.pk)
        empty = {"collections": {}, "books": {}}
        assert page_row_shelves(AnonymousUser(), self._acl(), None, book_qs) == empty
        nobody = User.objects.create_user(username="nobody", password=TEST_PASSWORD)
        acl = self._acl(nobody)
        with self.assertNumQueries(1):
            result = page_row_shelves(nobody, acl, None, book_qs)
        assert result == empty

    def test_selection_lists_shelves_the_whole_selection_shares(self):
        """Metadata for several comics lists only the shelves they all share."""
        both = self._shelf("Both")
        self._put(both, "series", self.s1.pk)
        self._put(both, "comics", self.c2.pk)
        one = self._shelf("One")
        self._put(one, "comics", self.c2.pk)
        comic_pks = Comic.objects.filter(pk__in=(self.c1.pk, self.c2.pk))
        assert selection_shelves(self.user, comic_pks, 2) == [both.pk]
        assert selection_shelves(AnonymousUser(), comic_pks, 2) == []


class ShelfMembershipApiTestCase(ShelfTestCase):
    """The table rows and the metadata response carry the shelf pks."""

    @override
    def setUp(self) -> None:
        super().setUp()
        response = post_json(
            self.client, "patch", SETTINGS_URL, {"show": _SHOW_ALL, "viewMode": "table"}
        )
        assert response.status_code == HTTP_OK, response.content

    def _rows(self, url: str) -> list[dict]:
        response = self.client.get(url)
        assert response.status_code == HTTP_OK, response.content
        return v4(response)["rows"]

    def test_table_rows_carry_shelves_with_the_column(self):
        """``columns=shelved`` adds the shelf pks beside the flag, which agrees."""
        shelf = self._shelf()
        self._put(shelf, "series", self.s1.pk)
        rows = self._rows(f"/api/v4/browse/comics/{self.v1.pk}?page=1&columns=shelved")
        assert [(row["pk"], row["shelved"], row["shelves"]) for row in rows] == [
            (self.c1.pk, True, [shelf.pk])
        ]
        series_rows = self._rows(
            f"/api/v4/browse/series/{self.i1.pk}?page=1&columns=name,shelved"
        )
        assert [(row["pk"], row["shelves"]) for row in series_rows] == [
            (self.s1.pk, [shelf.pk])
        ]

    def test_table_rows_follow_a_membership_change(self):
        """A refetch after shelving sees the change, as the UI's reload does."""
        # The shelf already holds a series, so the refetch runs the very
        # same SQL as the first fetch: only the shelf item rows differ.
        shelf = self._shelf()
        self._put(shelf, "series", self.s2.pk)
        url = f"/api/v4/browse/comics/{self.v1.pk}?page=1&columns=shelved"
        assert [row["shelves"] for row in self._rows(url)] == [[]]
        metadata_url = f"/api/v4/browse/comics/{self.c1.pk}/metadata"
        assert v4(self.client.get(metadata_url))["shelves"] == []
        # Through the API, like the shelf menu.
        response = post_json(
            self.client,
            "patch",
            items_url(shelf.pk),
            {"add": {"series": [self.s1.pk]}},
        )
        assert response.status_code == HTTP_OK, response.content
        assert [row["shelves"] for row in self._rows(url)] == [[shelf.pk]]
        assert v4(self.client.get(metadata_url))["shelves"] == [shelf.pk]

    def test_shelved_flag_follows_a_membership_change(self):
        """The flag the column sorts by isn't served stale from the cache."""
        shelf = self._shelf()
        # Already holds a comic, so the refetch is byte-identical SQL.
        self._put(shelf, "comics", self.c2.pk)
        url = (
            f"/api/v4/browse/comics/{self.v1.pk}?page=1&columns=shelved"
            "&order_by=shelved"
        )
        assert [row["shelved"] for row in self._rows(url)] == [False]
        response = post_json(
            self.client,
            "patch",
            items_url(shelf.pk),
            {"add": {"comics": [self.c1.pk]}},
        )
        assert response.status_code == HTTP_OK, response.content
        assert [row["shelved"] for row in self._rows(url)] == [True]

    def test_table_rows_skip_shelves_without_the_column(self):
        """No shelved column, no shelf work and no ``shelves`` key."""
        self._put(self._shelf(), "series", self.s1.pk)
        rows = self._rows(f"/api/v4/browse/comics/{self.v1.pk}?page=1&columns=name")
        assert rows
        assert all("shelves" not in row for row in rows)

    def test_metadata_lists_shared_shelves(self):
        """``/metadata`` reports the shelves the selection shares."""
        shelf = self._shelf()
        self._put(shelf, "comics", self.c1.pk)
        response = self.client.get(f"/api/v4/browse/comics/{self.c1.pk}/metadata")
        assert response.status_code == HTTP_OK, response.content
        assert v4(response)["shelves"] == [shelf.pk]
        response = self.client.get(
            f"/api/v4/browse/comics/{self.c1.pk},{self.c2.pk}/metadata"
        )
        assert response.status_code == HTTP_OK, response.content
        assert v4(response)["shelves"] == []


class RowSerializerKeyingTestCase(SimpleTestCase):
    """Folder view lists folders and comics whose pks collide."""

    def test_collection_values_never_land_on_a_same_pk_comic(self):
        """Intersections and shelves key by row kind, not bare pk."""
        folder = SimpleNamespace(pk=1, nav_collection="folders", ids=[1], year=None)
        comic = SimpleNamespace(pk=1, nav_collection="comics", ids=None, year=2001)
        rows = BrowserPageSerializer().get_rows(
            {
                "columns": ("year", "shelved"),
                "collections": [folder],
                "books": [comic],
                "collection_intersections": {1: {"year": 1999}},
                "row_shelves": {"collections": {1: [5]}, "books": {1: [6]}},
            }
        )
        assert [(row["year"], row["shelves"]) for row in rows] == [
            (1999, [5]),
            (2001, [6]),
        ]

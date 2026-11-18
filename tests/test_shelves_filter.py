"""Tests for the shelves browser filter, the shelved sort and annotation."""

from typing import override

from django.contrib.auth.models import AnonymousUser, User

from codex.models import Comic, Folder, Library, Series, Shelf
from codex.models.settings import SettingsBrowser, SettingsBrowserFilters
from codex.views.auth import ComicACL
from codex.views.browser.shelf_membership import annotate_shelved
from tests.shelf_fixtures import (
    HTTP_BAD_REQUEST,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_OK,
    SAVED_URL,
    SETTINGS_URL,
    TEST_PASSWORD,
    TMP_DIR,
    ShelfTestCase,
    detail_url,
    post_json,
    v4,
)


class ShelfFilterTestCase(ShelfTestCase):
    """The ``shelves`` browser filter: persistence, privacy and transitivity."""

    @override
    def setUp(self) -> None:
        super().setUp()
        # Default ``show.imprints``/``show.volumes`` are off — surface them
        # so every level can be browsed and asserted.
        response = post_json(
            self.client,
            "patch",
            SETTINGS_URL,
            {
                "show": {
                    "publishers": True,
                    "imprints": True,
                    "series": True,
                    "volumes": True,
                }
            },
        )
        assert response.status_code == HTTP_OK, response.content

    def _filter_by(self, *shelves: Shelf) -> None:
        response = post_json(
            self.client,
            "patch",
            SETTINGS_URL,
            {"filters": {"shelves": [shelf.pk for shelf in shelves]}},
        )
        assert response.status_code == HTTP_OK, response.content

    def _collection_pks(self, collection: str, scope_pk: int = 0) -> list[int]:
        suffix = f"/{scope_pk}" if scope_pk else ""
        response = self.client.get(f"/api/v4/browse/{collection}{suffix}?page=1")
        assert response.status_code == HTTP_OK, response.content
        return [
            ids[0]
            for row in v4(response).get("collections", [])
            if (ids := row.get("ids"))
        ]

    def _book_pks(self, collection: str, scope_pk: int) -> list[int]:
        response = self.client.get(f"/api/v4/browse/{collection}/{scope_pk}?page=1")
        assert response.status_code == HTTP_OK, response.content
        return [book.get("pk") for book in v4(response).get("books", [])]

    def test_filter_round_trips_and_defaults_empty(self):
        """``filters.shelves`` defaults to ``[]`` and persists a selection."""
        assert v4(self.client.get(SETTINGS_URL))["filters"]["shelves"] == []
        shelf = self._shelf()
        self._filter_by(shelf)
        assert v4(self.client.get(SETTINGS_URL))["filters"]["shelves"] == [shelf.pk]

    def test_filter_off_passes_everything_through(self):
        """With no shelf selected, shelved and unshelved rows all show."""
        self._put(self._shelf(), "publishers", self.p1.pk)
        assert sorted(self._collection_pks("publishers")) == sorted(
            [self.p1.pk, self.p2.pk]
        )

    def test_shelved_publisher_lights_up_descendants(self):
        """Shelve P1 → its full subtree (I1/S1/V1/C1) passes the filter."""
        shelf = self._shelf()
        self._put(shelf, "publishers", self.p1.pk)
        self._filter_by(shelf)
        assert self._collection_pks("publishers") == [self.p1.pk]
        assert self._collection_pks("publishers", self.p1.pk) == [self.i1.pk]
        assert self._collection_pks("imprints", self.i1.pk) == [self.s1.pk]
        assert self._collection_pks("series", self.s1.pk) == [self.v1.pk]
        assert self._book_pks("volumes", self.v1.pk) == [self.c1.pk]

    def test_shelved_comic_lights_up_ancestors(self):
        """Shelve C1 → P1/I1/S1/V1 stay navigable down to C1."""
        shelf = self._shelf()
        self._put(shelf, "comics", self.c1.pk)
        self._filter_by(shelf)
        assert self._collection_pks("publishers") == [self.p1.pk]
        assert self._collection_pks("publishers", self.p1.pk) == [self.i1.pk]
        assert self._collection_pks("imprints", self.i1.pk) == [self.s1.pk]
        assert self._collection_pks("series", self.s1.pk) == [self.v1.pk]
        assert self._book_pks("volumes", self.v1.pk) == [self.c1.pk]

    def test_shelved_series_isolates_unrelated_branch(self):
        """Shelve S1 → S2's subtree stays out."""
        shelf = self._shelf()
        self._put(shelf, "series", self.s1.pk)
        self._filter_by(shelf)
        assert self._collection_pks("publishers") == [self.p1.pk]
        assert self._collection_pks("imprints", self.i2.pk) == []
        assert self._collection_pks("series", self.s1.pk) == [self.v1.pk]
        assert self._book_pks("volumes", self.v1.pk) == [self.c1.pk]

    def test_two_shelves_match_items_on_either(self):
        """Selecting several shelves is an OR, like the tag filters."""
        first = self._shelf("First")
        second = self._shelf("Second")
        self._put(first, "series", self.s1.pk)
        self._put(second, "comics", self.c2.pk)

        self._filter_by(first)
        assert self._collection_pks("publishers") == [self.p1.pk]
        self._filter_by(first, second)
        assert sorted(self._collection_pks("publishers")) == sorted(
            [self.p1.pk, self.p2.pk]
        )

    def test_empty_shelf_matches_nothing(self):
        """Filtering by a shelf with no items shows no rows."""
        self._filter_by(self._shelf())
        assert self._collection_pks("publishers") == []

    def test_another_users_shelf_pk_matches_nothing(self):
        """A shelf pk the caller does not own never widens the filter."""
        other = User.objects.create_user(username="other", password=TEST_PASSWORD)
        theirs = self._shelf("Theirs", user=other)
        self._put(theirs, "publishers", self.p1.pk)
        mine = self._shelf("Mine")
        self._put(mine, "publishers", self.p2.pk)

        self._filter_by(theirs)
        assert self._collection_pks("publishers") == []
        self._filter_by(theirs, mine)
        assert self._collection_pks("publishers") == [self.p2.pk]

    def test_shelved_folder_lights_up_empty_intermediate_descendants(self):
        """Shelve a top folder → nested sub-folders surface, empty mids included."""
        # ``Comic.folders`` is the m2m of *all* ancestor folders for a
        # comic (the importer adds the full path chain), so a Folder with
        # no direct comics but a comic nested deeper still lights up. The
        # transitive shelf filter relies on this; pin it.
        library_dir = TMP_DIR / "ftree"
        f1_dir = library_dir / "a"
        f2_dir = f1_dir / "b"
        f3_dir = f2_dir / "c"
        # Folder.save() stats the path, so the directories must exist.
        f3_dir.mkdir(parents=True, exist_ok=True)
        library = Library.objects.create(path=str(library_dir))
        f1 = Folder.objects.create(library=library, path=str(f1_dir))
        f2 = Folder.objects.create(library=library, parent_folder=f1, path=str(f2_dir))
        f3 = Folder.objects.create(library=library, parent_folder=f2, path=str(f3_dir))
        comic_path = f3_dir / "deep.cbz"
        comic_path.touch()
        deep_comic = Comic.objects.create(
            library=library,
            path=comic_path,
            issue_number=1,
            name="deep",
            publisher=self.p1,
            imprint=self.i1,
            series=self.s1,
            volume=self.v1,
            parent_folder=f3,
            size=1,
        )
        deep_comic.folders.set([f1, f2, f3])

        shelf = self._shelf()
        self._put(shelf, "folders", f1.pk)
        self._filter_by(shelf)

        assert f1.pk in self._collection_pks("folders")
        children = self._collection_pks("folders", f1.pk)
        assert f2.pk in children, children

    def test_table_view_sort_by_shelved_does_not_crash(self):
        """Table view + ``order_by=shelved`` returns 200 at every level."""
        # ``shelved`` is annotated by ``_add_table_view_shelved_annotation``
        # for every browse model; the order pipeline must reuse that
        # annotation. Comic and collection querysets take different code
        # paths, so walk them all.
        self._put(self._shelf(), "series", self.s1.pk)
        response = post_json(
            self.client,
            "patch",
            SETTINGS_URL,
            {"viewMode": "table", "orderBy": "shelved", "orderReverse": True},
        )
        assert response.status_code == HTTP_OK, response.content
        for url in (
            "/api/v4/browse/publishers?page=1",
            f"/api/v4/browse/imprints/{self.p1.pk}?page=1",
            f"/api/v4/browse/series/{self.i1.pk}?page=1",
            f"/api/v4/browse/volumes/{self.s1.pk}?page=1",
            f"/api/v4/browse/comics/{self.v1.pk}?page=1",
        ):
            listing = self.client.get(url)
            assert listing.status_code == HTTP_OK, (url, listing.content)

    def test_cover_view_sort_by_shelved_falls_back_to_name(self):
        """
        Outside table view ``shelved`` is not annotated: sort by name.

        The order pipeline referenced the missing annotation.
        """
        self._put(self._shelf(), "series", self.s1.pk)
        response = post_json(
            self.client,
            "patch",
            SETTINGS_URL,
            {"viewMode": "cover", "orderBy": "shelved", "orderReverse": False},
        )
        assert response.status_code == HTTP_OK, response.content
        for url in (
            "/api/v4/browse/publishers?page=1",
            f"/api/v4/browse/comics/{self.v1.pk}?page=1",
        ):
            listing = self.client.get(url)
            assert listing.status_code == HTTP_OK, (url, listing.content)
        names = [
            row["name"]
            for row in v4(self.client.get("/api/v4/browse/publishers?page=1"))[
                "collections"
            ]
        ]
        assert names == sorted(names), names

    def test_retired_favorite_sort_key_is_rejected(self):
        """``favorite`` is no longer a sort key."""
        response = post_json(
            self.client, "patch", SETTINGS_URL, {"orderBy": "favorite"}
        )
        assert response.status_code == HTTP_BAD_REQUEST

    def test_deleting_a_shelf_clears_it_from_stored_filters(self):
        """Live settings and saved views stop filtering on a deleted shelf."""
        keep = self._shelf("Keep")
        gone = self._shelf("Gone")
        self._filter_by(keep, gone)
        saved = post_json(self.client, "post", SAVED_URL, {"name": "both"})
        assert saved.status_code == HTTP_CREATED, saved.content

        assert self.client.delete(detail_url(gone.pk)).status_code == HTTP_NO_CONTENT

        stored = SettingsBrowserFilters.objects.filter(browser__user=self.user)
        assert stored.count() >= 2  # noqa: PLR2004
        for filters in stored:
            assert filters.shelves == [keep.pk]

    def test_loading_a_saved_view_strips_a_stale_shelf_pk(self):
        """A saved view holding a shelf pk that no longer exists heals on load."""
        shelf = self._shelf()
        self._filter_by(shelf)
        saved = post_json(self.client, "post", SAVED_URL, {"name": "stale"})
        assert saved.status_code == HTTP_CREATED, saved.content
        saved_row = SettingsBrowser.objects.get(user=self.user, name="stale")
        # Bypass the API, which would clean the row itself on delete.
        Shelf.objects.filter(pk=shelf.pk).delete()

        loaded = self.client.get(f"{SAVED_URL}/{saved_row.pk}")
        assert loaded.status_code == HTTP_OK, loaded.content
        body = v4(loaded)
        assert body["settings"]["filters"]["shelves"] == []
        assert "shelves" in body["filterWarnings"]
        assert SettingsBrowserFilters.objects.get(browser=saved_row).shelves == []

    def test_a_saved_view_keeps_only_its_owners_shelves(self):
        """
        A shelf pk is checked against the viewer's shelves, not all of them.

        Checking it globally made loading a saved view an existence oracle
        for other users' shelves.
        """
        mine = self._shelf()
        other = User.objects.create_user(username="other", password=TEST_PASSWORD)
        theirs = self._shelf(name="Theirs", user=other)
        self._filter_by(mine)
        saved = post_json(self.client, "post", SAVED_URL, {"name": "mixed"})
        assert saved.status_code == HTTP_CREATED, saved.content
        saved_row = SettingsBrowser.objects.get(user=self.user, name="mixed")
        SettingsBrowserFilters.objects.filter(browser=saved_row).update(
            shelves=[mine.pk, theirs.pk]
        )

        loaded = self.client.get(f"{SAVED_URL}/{saved_row.pk}")
        assert loaded.status_code == HTTP_OK, loaded.content
        body = v4(loaded)
        assert body["settings"]["filters"]["shelves"] == [mine.pk]
        assert "shelves" in body["filterWarnings"]


class ShelvedAnnotationTestCase(ShelfTestCase):
    """``annotate_shelved`` is true for rows on any of the user's shelves."""

    @staticmethod
    def _acl(user) -> ComicACL:
        return ComicACL.for_user(user)

    def test_authenticated_user_gets_per_row_flag(self):
        """Rows on any of the user's shelves are True; the rest False."""
        self._put(self._shelf("One"), "series", self.s1.pk)
        other = User.objects.create_user(username="other", password=TEST_PASSWORD)
        self._put(self._shelf("Theirs", user=other), "series", self.s2.pk)

        qs = annotate_shelved(Series.objects.all(), self.user, self._acl(self.user))
        rows = dict(qs.values_list("pk", "shelved"))
        assert rows[self.s1.pk] is True
        assert rows[self.s2.pk] is False

    def test_anonymous_user_gets_constant_false(self):
        """Anonymous sessions own no shelves."""
        self._put(self._shelf(), "series", self.s1.pk)
        anon = AnonymousUser()
        qs = annotate_shelved(Series.objects.all(), anon, self._acl(anon))
        rows = dict(qs.values_list("pk", "shelved"))
        assert all(value is False for value in rows.values())

    def test_unmapped_model_returns_empty_dict(self):
        """A model that cannot be shelved contributes no annotation."""
        qs = annotate_shelved(Library.objects.all(), self.user, self._acl(self.user))
        assert "shelved" not in qs.query.annotations

"""HTTP-level tests for the favorites API."""

import json
import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.models import (
    Comic,
    Favorite,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_HTTP_CREATED: Final = 201
_HTTP_NO_CONTENT: Final = 204
_HTTP_BAD_REQUEST: Final = 400
_HTTP_FORBIDDEN: Final = 403
_HTTP_NOT_FOUND: Final = 404

_LIST_URL: Final = "/api/v4/favorites/"
_TMP_DIR: Final = Path("/tmp/codex.tests.fav")  # noqa: S108

_GROUP_TO_COLLECTION: Final = {
    "p": "publishers",
    "i": "imprints",
    "s": "series",
    "v": "volumes",
    "c": "comics",
    "f": "folders",
    "a": "arcs",
}

# v3 navigation group → v4 collection used by the transitivity tests.
# The collection segment names the *current* nav level (matching v3's
# single-char ``group`` kwarg); v3 ``r`` (root) is the only special
# case — the v4 plan drops it, so root listings spell as
# ``/api/v4/browse/publishers`` and the dispatcher fills in
# ``group="p", pks=()`` for the v3 body to handle.
_NAV_COLLECTION: Final = {
    "r": "publishers",
    "p": "publishers",
    "i": "imprints",
    "s": "series",
    "v": "volumes",
    "f": "folders",
    "a": "arcs",
}


def _detail_url(group: str, target_id: int) -> str:
    collection = _GROUP_TO_COLLECTION.get(group, group)
    return f"{_LIST_URL}{collection}/{target_id}"


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


class FavoritesAPITestCase(TestCase):
    """End-to-end favorites HTTP exercises against an authenticated client."""

    @override
    def setUp(self) -> None:
        """Provision an authenticated client + one of each favorite-able row."""
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        comic_path = _TMP_DIR / "x.cbz"
        comic_path.touch()

        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="favapi", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

        library = Library.objects.create(path=str(_TMP_DIR))
        publisher = Publisher.objects.create(name="P")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        comic = Comic.objects.create(
            library=library,
            path=comic_path,
            issue_number=1,
            name="x",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=1,
        )
        self.publisher_pk = publisher.pk  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series_pk = series.pk  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic_pk = comic.pk  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self) -> None:
        """Clean up the touch file."""
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_put_creates_then_idempotent(self):
        """First PUT returns 201; second PUT on same target returns 200."""
        first = self.client.put(_detail_url("s", self.series_pk))
        assert first.status_code == _HTTP_CREATED
        second = self.client.put(_detail_url("s", self.series_pk))
        assert second.status_code == _HTTP_OK
        assert (
            Favorite.objects.filter(
                user=self.user, collection="series", target_id=self.series_pk
            ).count()
            == 1
        )

    def test_delete_idempotent(self):
        """DELETE returns 204 whether or not the row existed."""
        self.client.put(_detail_url("c", self.comic_pk))
        first = self.client.delete(_detail_url("c", self.comic_pk))
        assert first.status_code == _HTTP_NO_CONTENT
        second = self.client.delete(_detail_url("c", self.comic_pk))
        assert second.status_code == _HTTP_NO_CONTENT

    def test_put_404_for_unknown_target(self):
        """A target_id that doesn't exist must 404, not 201."""
        bogus_pk = self.series_pk + 99999
        response = self.client.put(_detail_url("s", bogus_pk))
        assert response.status_code == _HTTP_NOT_FOUND
        assert not Favorite.objects.filter(
            collection="series", target_id=bogus_pk
        ).exists()

    def test_put_unmapped_group_does_not_match_route(self):
        """
        The v4 collection converter only matches the seven collection names.

        Anything else falls through to the SPA catch-all (the URL is not a
        favorites endpoint at all), so we get the catch-all's 302 → ``/``
        rather than a 404 from the view. Either way no Favorite is written.
        """
        response = self.client.put("/api/v4/favorites/unknowngroup/1")
        assert response.status_code in {302, 404}
        assert not Favorite.objects.filter(target_id=1).exists()

    def test_get_returns_favorites_grouped_by_code(self):
        """GET groups the user's favorites by collection name."""
        self.client.put(_detail_url("s", self.series_pk))
        self.client.put(_detail_url("p", self.publisher_pk))
        response = self.client.get(_LIST_URL)
        assert response.status_code == _HTTP_OK
        body = _v4(response)
        assert sorted(body["series"]) == [self.series_pk]
        assert sorted(body["publishers"]) == [self.publisher_pk]
        # Untouched groups must still be present (empty list).
        assert body["comics"] == []
        assert body["volumes"] == []

    def test_get_only_returns_requesting_user_favorites(self):
        """A second user's favorites must not leak through GET."""
        other = User.objects.create_user(username="favapi2", password=_TEST_PASSWORD)
        Favorite.objects.create(
            user=other, collection="series", target_id=self.series_pk
        )
        response = self.client.get(_LIST_URL)
        assert response.status_code == _HTTP_OK
        assert _v4(response)["series"] == []

    def test_anonymous_forbidden(self):
        """Logged-out clients must not reach the favorites surface."""
        anon = Client()
        list_resp = anon.get(_LIST_URL)
        assert list_resp.status_code == _HTTP_FORBIDDEN
        put_resp = anon.put(_detail_url("s", self.series_pk))
        assert put_resp.status_code == _HTTP_FORBIDDEN
        delete_resp = anon.delete(_detail_url("s", self.series_pk))
        assert delete_resp.status_code == _HTTP_FORBIDDEN

    def test_get_payload_is_json(self):
        """Sanity: GET returns a JSON object."""
        response = self.client.get(_LIST_URL)
        body = _v4(response)
        assert isinstance(body, dict)
        assert set(body) >= {
            "publishers",
            "imprints",
            "series",
            "volumes",
            "folders",
            "arcs",
            "comics",
        }


_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"


class FavoriteFilterTestCase(TestCase):
    """Browser favorite filter: round-trip persistence and queryset narrowing."""

    @override
    def setUp(self) -> None:
        """Build two series and favorite the first one."""
        from codex.startup import init_admin_flags

        init_admin_flags()

        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="favfilter", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

        publisher = Publisher.objects.create(name="P")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        self.fav_series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="favored", publisher=publisher, imprint=imprint
        )
        self.other_series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="ignored", publisher=publisher, imprint=imprint
        )
        Favorite.objects.create(
            user=self.user, collection="series", target_id=self.fav_series.pk
        )

    def test_favorite_filter_round_trips_via_settings(self):
        """PATCH ``filters.favorite=true`` persists and re-emits as True."""
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"filters": {"favorite": True}}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        get_resp = self.client.get(_SETTINGS_URL)
        assert get_resp.status_code == _HTTP_OK
        assert _v4(get_resp)["filters"]["favorite"] is True

    def test_favorite_filter_default_is_false(self):
        """Fresh settings expose ``filters.favorite`` as False."""
        get_resp = self.client.get(_SETTINGS_URL)
        assert get_resp.status_code == _HTTP_OK
        assert _v4(get_resp)["filters"]["favorite"] is False

    def test_favorite_subquery_narrows_to_favorited_pks(self):
        """The pk__in subquery restricts the queryset to the user's favorites."""
        favorited = Favorite.objects.filter(user=self.user, collection="series").values(
            "target_id"
        )
        narrowed = Series.objects.filter(pk__in=favorited).values_list("pk", flat=True)
        assert list(narrowed) == [self.fav_series.pk]
        assert self.other_series.pk not in narrowed


class FavoriteFilterTransitivityTestCase(TestCase):
    """Browser favorite filter: hierarchical descent + ascent through the comic chain."""

    @override
    def setUp(self) -> None:
        """Provision two parallel hierarchies P1/I1/S1/V1/C1 and P2/I2/S2/V2/C2."""
        from django.core.cache import cache

        from codex.startup import init_admin_flags

        # Browser views go through cachalot. Clearing the per-request
        # cache between tests prevents an earlier test's Publisher
        # list (cached against a different user / settings combo)
        # from masking the current test's expected result.
        cache.clear()
        init_admin_flags()
        _TMP_DIR.mkdir(exist_ok=True, parents=True)

        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="favtransit", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

        library = Library.objects.create(path=str(_TMP_DIR))
        self.p1, self.i1, self.s1, self.v1, self.c1 = self._make_chain(library, "1")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.p2, self.i2, self.s2, self.v2, self.c2 = self._make_chain(library, "2")  # pyright: ignore[reportUninitializedInstanceVariable]
        # Default ``show.i``/``show.v`` are False — surface them so we
        # can browse and assert at every group level without juggling
        # the auto-collapse the browser does for hidden levels.
        self._patch_show_all()

    @override
    def tearDown(self) -> None:
        """Clean up the touch files."""
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _make_chain(self, library: Library, suffix: str):
        publisher = Publisher.objects.create(name=f"P{suffix}")
        imprint = Imprint.objects.create(name=f"I{suffix}", publisher=publisher)
        series = Series.objects.create(
            name=f"S{suffix}", publisher=publisher, imprint=imprint
        )
        volume = Volume.objects.create(
            name=suffix, publisher=publisher, imprint=imprint, series=series
        )
        path = _TMP_DIR / f"c{suffix}.cbz"
        path.touch()
        comic = Comic.objects.create(
            library=library,
            path=path,
            issue_number=int(suffix),
            name=f"C{suffix}",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=1,
        )
        return publisher, imprint, series, volume, comic

    def _patch_show_all(self) -> None:
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps(
                {
                    "show": {
                        "publishers": True,
                        "imprints": True,
                        "series": True,
                        "volumes": True,
                    }
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _enable_favorite_filter(self) -> None:
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"filters": {"favorite": True}}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _collection_pks(self, group: str, scope_pk: int = 0) -> list[int]:
        collection = _NAV_COLLECTION[group]
        suffix = f"/{scope_pk}" if scope_pk else ""
        url = f"/api/v4/browse/{collection}{suffix}?page=1"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        # Group rows surface in ``groups`` (each entry has ``ids`` for
        # multi-pk rollups; in this fixture every chain has one row).
        return [
            ids[0]
            for g in _v4(response).get("collections", [])
            if (ids := g.get("ids"))
        ]

    def _book_pks(self, group: str, scope_pk: int) -> list[int]:
        collection = _NAV_COLLECTION[group]
        suffix = f"/{scope_pk}" if scope_pk else ""
        url = f"/api/v4/browse/{collection}{suffix}?page=1"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return [b.get("pk") for b in _v4(response).get("books", [])]

    def test_favorited_publisher_lights_up_descendant_groups(self):
        """Favorite P1 → its full subtree (I1/S1/V1/C1) passes the filter."""
        Favorite.objects.create(
            user=self.user, collection="publishers", target_id=self.p1.pk
        )
        self._enable_favorite_filter()
        # Publisher list: only P1.
        assert self._collection_pks("r") == [self.p1.pk]
        # Imprint list under P1: I1.
        assert self._collection_pks("p", self.p1.pk) == [self.i1.pk]
        # Series list under I1: S1.
        assert self._collection_pks("i", self.i1.pk) == [self.s1.pk]
        # Volume list under S1: V1.
        assert self._collection_pks("s", self.s1.pk) == [self.v1.pk]
        # Comic list under V1: C1.
        assert self._book_pks("v", self.v1.pk) == [self.c1.pk]

    def test_favorited_comic_lights_up_ancestor_groups(self):
        """Favorite C1 → P1/I1/S1/V1 still navigable down to C1."""
        Favorite.objects.create(
            user=self.user, collection="comics", target_id=self.c1.pk
        )
        self._enable_favorite_filter()
        assert self._collection_pks("r") == [self.p1.pk]
        assert self._collection_pks("p", self.p1.pk) == [self.i1.pk]
        assert self._collection_pks("i", self.i1.pk) == [self.s1.pk]
        assert self._collection_pks("s", self.s1.pk) == [self.v1.pk]
        assert self._book_pks("v", self.v1.pk) == [self.c1.pk]

    def test_favorited_series_isolates_unrelated_branch(self):
        """Favorite S1 → S2's subtree stays out; S1's ancestors and C1 surface."""
        Favorite.objects.create(
            user=self.user, collection="series", target_id=self.s1.pk
        )
        self._enable_favorite_filter()
        # Publishers: only P1.
        assert self._collection_pks("r") == [self.p1.pk]
        # Series under P2's imprint should be empty (filter narrows P2 out
        # at the publisher level — descending into I2 returns no rows).
        assert self._collection_pks("i", self.i2.pk) == []
        # Volumes under S1: V1 surfaces (so the user can drill to C1).
        assert self._collection_pks("s", self.s1.pk) == [self.v1.pk]
        # Comic under V1: C1 surfaces.
        assert self._book_pks("v", self.v1.pk) == [self.c1.pk]

    def test_filter_off_passes_everything_through(self):
        """Sanity: with the filter off, every chain row shows."""
        Favorite.objects.create(
            user=self.user, collection="publishers", target_id=self.p1.pk
        )
        # Filter not enabled. Both P1 and P2 should appear.
        assert sorted(self._collection_pks("r")) == sorted([self.p1.pk, self.p2.pk])

    def test_favorited_folder_lights_up_empty_intermediate_descendants(self):
        """Favorite a top folder → every nested sub-folder surfaces, empty mids included."""
        # ``Comic.folders`` is the m2m of *all* ancestor folders for a
        # comic (the importer adds the full path chain). The reverse
        # accessor ``Folder.comic`` traverses that m2m, so a Folder
        # with no direct parent_folder children but a comic descendant
        # nested deeper still reports comics — and ``comic__folders``
        # lights up its ancestors. The transitive favorite filter
        # relies on this; pin it.
        library_dir = _TMP_DIR / "ftree"
        f1_dir = library_dir / "a"
        f2_dir = f1_dir / "b"
        f3_dir = f2_dir / "c"
        # Folder.save() stats the path, so the directories have to
        # exist on disk before the rows are created.
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
        # Mirror the importer: Comic.folders carries every ancestor in
        # the path chain, not just the direct parent.
        deep_comic.folders.set([f1, f2, f3])

        Favorite.objects.create(user=self.user, collection="folders", target_id=f1.pk)
        self._enable_favorite_filter()

        # Top-level folder list: F1 surfaces (self) and any
        # descendants the filter pulls in.
        top = self._collection_pks("f")
        assert f1.pk in top
        # Inside F1, the empty intermediate F2 must surface so the
        # user can keep drilling toward the deep comic.
        children = self._collection_pks("f", f1.pk)
        assert f2.pk in children, children

    def test_table_view_sort_by_favorite_does_not_crash(self):
        """Table view + ``order_by=favorite`` on a group list returns 200."""
        # ``favorite`` is annotated by ``_add_table_view_favorite_annotation``
        # for every browse model; the order pipeline must reuse that
        # annotation rather than dispatching to ``_ORDER_AGGREGATE_FUNCS``
        # (which would KeyError because ``favorite`` is annotated, not
        # aggregated). Pin the no-crash invariant for the primary key
        # at every group level — Comic and collection queryset take
        # different code paths.
        Favorite.objects.create(
            user=self.user, collection="series", target_id=self.s1.pk
        )
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps(
                {
                    "viewMode": "table",
                    "orderBy": "favorite",
                    "orderReverse": True,
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        for url in (
            "/api/v4/browse/publishers?page=1",
            f"/api/v4/browse/imprints/{self.p1.pk}?page=1",
            f"/api/v4/browse/series/{self.i1.pk}?page=1",
            f"/api/v4/browse/volumes/{self.s1.pk}?page=1",
            f"/api/v4/browse/comics/{self.v1.pk}?page=1",
        ):
            r = self.client.get(url)
            assert r.status_code == _HTTP_OK, (url, r.content)


class FavoriteAnnotationTestCase(TestCase):
    """``favorite_annotation_for`` produces the right Exists/Value shape per case."""

    @override
    def setUp(self) -> None:
        from django.contrib.auth.models import AnonymousUser

        self.anon = AnonymousUser()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="annotator", password=_TEST_PASSWORD
        )
        publisher = Publisher.objects.create(name="P")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        self.fav_series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="favored", publisher=publisher, imprint=imprint
        )
        self.other_series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="ignored", publisher=publisher, imprint=imprint
        )
        Favorite.objects.create(
            user=self.user, collection="series", target_id=self.fav_series.pk
        )

    def test_authenticated_user_gets_per_row_exists(self):
        """Annotated queryset reports True for favorited rows, False otherwise."""
        from codex.views.browser.columns import favorite_annotation_for

        annotations = favorite_annotation_for(Series, self.user)
        assert "favorite" in annotations

        rows = dict(
            Series.objects.annotate(**annotations).values_list("pk", "favorite")
        )
        assert rows[self.fav_series.pk] is True
        assert rows[self.other_series.pk] is False

    def test_anonymous_user_gets_constant_false(self):
        """Anonymous user → ``Value(False)``; every row has favorite=False."""
        from codex.views.browser.columns import favorite_annotation_for

        annotations = favorite_annotation_for(Series, self.anon)
        rows = dict(
            Series.objects.annotate(**annotations).values_list("pk", "favorite")
        )
        assert all(v is False for v in rows.values())

    def test_unmapped_model_returns_empty_dict(self):
        """A non-favorite-able model contributes no annotation."""
        from codex.views.browser.columns import favorite_annotation_for

        # Library is a real model but not in the favorite group map.
        annotations = favorite_annotation_for(Library, self.user)
        assert annotations == {}

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

_LIST_URL: Final = "/api/v3/favorites/"
_TMP_DIR: Final = Path("/tmp/codex.tests.fav")  # noqa: S108


def _detail_url(group: str, target_id: int) -> str:
    return f"{_LIST_URL}{group}/{target_id}/"


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
                user=self.user, group="s", target_id=self.series_pk
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
        assert not Favorite.objects.filter(group="s", target_id=bogus_pk).exists()

    def test_put_400_for_unmapped_group(self):
        """The URL converter accepts ``r`` but the view has no model for it."""
        response = self.client.put(_detail_url("r", 1))
        assert response.status_code == _HTTP_BAD_REQUEST

    def test_get_returns_favorites_grouped_by_code(self):
        """GET groups the user's favorites by single-letter group code."""
        self.client.put(_detail_url("s", self.series_pk))
        self.client.put(_detail_url("p", self.publisher_pk))
        response = self.client.get(_LIST_URL)
        assert response.status_code == _HTTP_OK
        body = response.json()
        assert sorted(body["s"]) == [self.series_pk]
        assert sorted(body["p"]) == [self.publisher_pk]
        # Untouched groups must still be present (empty list).
        assert body["c"] == []
        assert body["v"] == []

    def test_get_only_returns_requesting_user_favorites(self):
        """A second user's favorites must not leak through GET."""
        other = User.objects.create_user(username="favapi2", password=_TEST_PASSWORD)
        Favorite.objects.create(user=other, group="s", target_id=self.series_pk)
        response = self.client.get(_LIST_URL)
        assert response.status_code == _HTTP_OK
        assert response.json()["s"] == []

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
        body = json.loads(response.content)
        assert isinstance(body, dict)
        assert set(body) >= {"p", "i", "s", "v", "f", "a", "c"}


_SETTINGS_URL: Final = "/api/v3/r/settings"


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
        Favorite.objects.create(user=self.user, group="s", target_id=self.fav_series.pk)

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
        assert get_resp.json()["filters"]["favorite"] is True

    def test_favorite_filter_default_is_false(self):
        """Fresh settings expose ``filters.favorite`` as False."""
        get_resp = self.client.get(_SETTINGS_URL)
        assert get_resp.status_code == _HTTP_OK
        assert get_resp.json()["filters"]["favorite"] is False

    def test_favorite_subquery_narrows_to_favorited_pks(self):
        """The pk__in subquery restricts the queryset to the user's favorites."""
        favorited = Favorite.objects.filter(user=self.user, group="s").values(
            "target_id"
        )
        narrowed = Series.objects.filter(pk__in=favorited).values_list("pk", flat=True)
        assert list(narrowed) == [self.fav_series.pk]
        assert self.other_series.pk not in narrowed


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
            user=self.user, group="s", target_id=self.fav_series.pk
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

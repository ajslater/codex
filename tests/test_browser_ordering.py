"""
Tests for the expanded ``order_by`` enum.

Phase 1 / Step 4 added 20 new entries to ``BROWSER_ORDER_BY_CHOICES``.
The new keys split into two categories:

- direct Comic fields (``year``, ``month``, ``issue_number``, etc.)
- FK-name keys translated to ORM paths via ``comic_order_path``
  (``series_name`` -> ``series__name``, etc.)

These tests confirm:
- the serializer accepts every new key,
- the registry's ``sort_key`` references stay consistent with the enum,
- representative ordering paths produce the expected sequence end-to-end
  through the HTTP browser endpoint.
"""

import json
import shutil
from pathlib import Path
from typing import Final, override

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.choices.browser import BROWSER_ORDER_BY_CHOICES, BROWSER_TABLE_COLUMNS
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.models.collections import Folder
from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.startup import init_admin_flags
from codex.views.browser.order_by import (
    COMIC_ORDER_FIELD_PATHS,
    comic_order_path,
)

_NEW_ORDER_BY_KEYS: Final = (
    "country",
    "day",
    "file_type",
    "imprint_name",
    "issue",
    "language",
    "main_character",
    "main_team",
    "metadata_mtime",
    "month",
    "monochrome",
    "original_format",
    "publisher_name",
    "reading_direction",
    "scan_info",
    "series_name",
    "tagger",
    "volume_name",
    "year",
)
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
TMP_DIR = Path("/tmp/codex.tests.browser_ordering")  # noqa: S108
_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


@pytest.mark.parametrize("key", _NEW_ORDER_BY_KEYS)
def test_new_order_by_key_in_enum(key: str) -> None:
    """Every key shipped in Step 4 is in ``BROWSER_ORDER_BY_CHOICES``."""
    assert key in BROWSER_ORDER_BY_CHOICES


@pytest.mark.parametrize("key", _NEW_ORDER_BY_KEYS)
def test_serializer_accepts_new_order_by(key: str) -> None:
    """The settings serializer's order_by ChoiceField accepts every new key."""
    s = BrowserSettingsSerializer(data={"order_by": key})
    assert s.is_valid(), s.errors


def test_registry_sortable_columns_resolve_to_enum() -> None:
    """Every sortable registry entry's sort_key resolves into the enum."""
    for column_key, entry in BROWSER_TABLE_COLUMNS.items():
        sort_key = entry["sort_key"]
        if sort_key is None:
            continue
        assert sort_key in BROWSER_ORDER_BY_CHOICES, (
            f"column {column_key} sort_key {sort_key!r} not in order_by enum"
        )


def test_comic_order_path_translates_fk_names() -> None:
    """FK-name keys translate to ``__name`` ORM paths."""
    assert comic_order_path("series_name") == "series__name"
    assert comic_order_path("publisher_name") == "publisher__name"
    assert comic_order_path("country") == "country__name"
    assert comic_order_path("language") == "language__name"


def test_comic_order_path_passes_through_unknown() -> None:
    """Keys not in the FK map are returned unchanged (Comic field name)."""
    assert comic_order_path("year") == "year"
    assert comic_order_path("issue_number") == "issue_number"
    assert comic_order_path("page_count") == "page_count"


def test_comic_order_field_paths_target_name() -> None:
    """
    Every translated path ends in ``__name``.

    Exception: the virtual ``issue`` key maps to the underlying
    ``issue_number`` field (the suffix secondary is added in
    ``_add_comic_order_by``, not by this map).
    """
    for key, path in COMIC_ORDER_FIELD_PATHS.items():
        if key == "issue":
            assert path == "issue_number"
            continue
        assert path.endswith("__name"), f"{key} -> {path}"


class BrowserOrderByIntegrationTestCase(TestCase):
    """Smoke-test the browser page endpoint with the new order_by keys."""

    @override
    def setUp(self) -> None:
        # ``cache_page`` on the browser endpoint keys on URL only — without
        # this clear, tests bleed cached responses across each other and a
        # PATCH to settings won't be reflected in the next GET.
        cache.clear()
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))

        publisher = Publisher.objects.create(name="ZZ Press")
        imprint = Imprint.objects.create(name="ZZ Imprint", publisher=publisher)
        series_a = Series.objects.create(
            name="Alpha", imprint=imprint, publisher=publisher
        )
        series_b = Series.objects.create(
            name="Beta", imprint=imprint, publisher=publisher
        )
        volume_a = Volume.objects.create(
            name="2020", series=series_a, imprint=imprint, publisher=publisher
        )
        volume_b = Volume.objects.create(
            name="2021", series=series_b, imprint=imprint, publisher=publisher
        )

        def _comic(suffix: str, ser, vol, year: int, issue: int) -> Comic:
            path = TMP_DIR / f"{suffix}.cbz"
            path.touch()
            return Comic.objects.create(
                library=library,
                path=path,
                issue_number=issue,
                name=suffix,
                publisher=publisher,
                imprint=imprint,
                series=ser,
                volume=vol,
                size=100 + issue,
                year=year,
                page_count=10 + issue,
            )

        self.comic_alpha_1 = _comic("a1", series_a, volume_a, 2020, 1)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic_alpha_2 = _comic("a2", series_a, volume_a, 2020, 2)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic_beta_1 = _comic("b1", series_b, volume_b, 2021, 1)  # pyright: ignore[reportUninitializedInstanceVariable]
        user = User.objects.create_user(
            username="ordering_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _patch_order_by(self, key: str, *, reverse: bool = False) -> None:
        response = self.client.patch(
            _SETTINGS_URL,
            data=f'{{"orderBy":"{key}","orderReverse":{str(reverse).lower()}}}',
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _patch_settings(self, payload: dict) -> None:
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _browse_comics(self) -> list[int]:
        # Browse the Series containing the alpha comics; with the default
        # ``show.v == False`` the response flattens to direct comic books.
        # v4 strips ``books`` from table-mode responses and ``rows`` from
        # cover-mode responses (tasks/api-v4.md Phase 3); read whichever
        # the active view mode emits so callers can pick the mode that
        # exercises the behavior under test.
        series_a = Series.objects.get(name="Alpha")
        url = f"/api/v4/browse/series/{series_a.pk}?page=1"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        body = _v4(response)
        items = body.get("books") or body.get("rows") or []
        return [item["pk"] for item in items]

    def test_year_ordering_smoke(self) -> None:
        """Sorting comics by year doesn't error and returns the expected pks."""
        self._patch_order_by("year")
        pks = self._browse_comics()
        assert set(pks) == {self.comic_alpha_1.pk, self.comic_alpha_2.pk}

    def test_issue_ordering(self) -> None:
        """Sorting comics by ``issue`` is ascending in pk order for alpha."""
        # ``issue`` is the compound order_by enum entry that expands to
        # ``[issue_number, issue_suffix]`` ORDER BY in the dispatcher.
        self._patch_order_by("issue")
        pks = self._browse_comics()
        assert pks == [self.comic_alpha_1.pk, self.comic_alpha_2.pk]

    def test_issue_reverse_ordering(self) -> None:
        """Sorting comics by ``issue`` reversed flips the alpha pair."""
        self._patch_order_by("issue", reverse=True)
        pks = self._browse_comics()
        expected = [self.comic_alpha_2.pk, self.comic_alpha_1.pk]
        assert pks == expected, f"got {pks}, expected {expected}"

    def test_multi_column_sort_extras_apply(self) -> None:
        """
        Multi-column sort: extras tail an ordered sequence onto the primary.

        Both alpha comics share ``year=2020``; the extras tail breaks
        the tie by ``issue`` (asc), giving us alpha_1 then alpha_2.
        Extras only kick in for table-view mode — cover view sticks
        to its toolbar dropdown and ignores extras even when they're
        persisted in settings.
        """
        self._patch_settings(
            {
                "viewMode": "table",
                "orderBy": "year",
                "orderReverse": False,
                "orderExtraKeys": [{"key": "issue", "reverse": False}],
            }
        )
        pks = self._browse_comics()
        assert pks == [self.comic_alpha_1.pk, self.comic_alpha_2.pk]

    def test_multi_column_sort_extras_reverse(self) -> None:
        """A reverse extra flips the tie-breaker direction."""
        self._patch_settings(
            {
                "viewMode": "table",
                "orderBy": "year",
                "orderReverse": False,
                "orderExtraKeys": [{"key": "issue", "reverse": True}],
            }
        )
        pks = self._browse_comics()
        assert pks == [self.comic_alpha_2.pk, self.comic_alpha_1.pk]

    def test_multi_column_sort_m2m_extra_does_not_crash(self) -> None:
        """
        Regression: M2M extras must annotate their alias upstream.

        Adding an M2M column (``genres``) as a secondary sort while
        the primary is a non-M2M key (``year``) used to crash with
        ``FieldError: Cannot resolve keyword '_table_m2m_genres'``
        because ``_add_table_view_sort_annotations`` only annotated
        the alias for the primary key. The fix collects every key
        from primary + extras into the annotation set.
        """
        self._patch_settings(
            {
                "viewMode": "table",
                "orderBy": "year",
                "orderReverse": False,
                "orderExtraKeys": [{"key": "genres", "reverse": False}],
            }
        )
        # Browse comics with ``genres`` in the visible column set so
        # the request matches what the table-view UI would send.
        url = (
            f"/api/v4/browse/series/{Series.objects.get(name='Alpha').pk}"
            "?page=1&columns=cover,name,issue,genres"
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content

    def test_multi_column_sort_extras_apply_to_group_rows(self) -> None:
        """
        Group-row queries (Series, Volume, Publisher, …) honor extras.

        Browse the publisher level, listing series rows. Both series
        share the publisher → primary ``publisher_name`` ties; the
        ``child_count`` extra (desc) breaks the tie so the series
        with more child comics (``Alpha``) sorts before the one with
        fewer (``Beta``). Sanity-check by flipping the extra to
        ``asc`` and asserting the order swaps.
        """
        publisher = Publisher.objects.get(name="ZZ Press")
        url = f"/api/v4/browse/publishers/{publisher.pk}?page=1"
        # Desc extra → larger child_count first. Extras only apply in
        # table view (cover dropdown can't add them); v4 strips
        # ``groups`` from table responses so the assertions read the
        # ``name`` projection off ``rows`` (tasks/api-v4.md Phase 3).
        self._patch_settings(
            {
                "viewMode": "table",
                "orderBy": "publisher_name",
                "orderReverse": False,
                "orderExtraKeys": [{"key": "child_count", "reverse": True}],
            }
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        names = [r.get("name") for r in _v4(response).get("rows", [])]
        assert names == ["Alpha", "Beta"], names

        # Asc extra → smaller child_count first.
        cache.clear()
        self._patch_settings(
            {
                "viewMode": "table",
                "orderBy": "publisher_name",
                "orderReverse": False,
                "orderExtraKeys": [{"key": "child_count", "reverse": False}],
            }
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        names = [r.get("name") for r in _v4(response).get("rows", [])]
        assert names == ["Beta", "Alpha"], names

    def test_multi_column_sort_filename_extra(self) -> None:
        """``filename`` works as an extra — was previously unsupported."""
        self._patch_settings(
            {
                "viewMode": "table",
                "orderBy": "year",
                "orderReverse": False,
                "orderExtraKeys": [{"key": "filename", "reverse": False}],
            }
        )
        # On Comic queries the extra resolves to a per-row Right(path)
        # expression, no aggregate. Smoke-test by hitting the endpoint
        # and confirming no crash + the expected row count.
        url = f"/api/v4/browse/series/{Series.objects.get(name='Alpha').pk}?page=1"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content

    def test_multi_column_sort_bookmark_updated_at_extra(self) -> None:
        """``bookmark_updated_at`` works as an extra (regression smoke)."""
        self._patch_settings(
            {
                "viewMode": "table",
                "orderBy": "year",
                "orderReverse": False,
                "orderExtraKeys": [
                    {"key": "bookmark_updated_at", "reverse": True},
                ],
            }
        )
        url = f"/api/v4/browse/series/{Series.objects.get(name='Alpha').pk}?page=1"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content

    def test_primary_sort_by_tagger_on_group_rows(self) -> None:
        """
        Group-row primary sort routes through ``annotate_order_value``.

        Regression: simple FK / scalar primaries (tagger, age_rating,
        size, page_count, country, language, …) used to sort group
        rows in PK order rather than by the aggregate of their
        children's values.
        """
        from codex.models.named import Tagger

        tagger_a = Tagger.objects.create(name="Alice")
        tagger_b = Tagger.objects.create(name="Bob")
        # alpha's comics get Alice; beta's only comic gets Bob.
        self.comic_alpha_1.tagger = tagger_a
        self.comic_alpha_1.save()
        self.comic_alpha_2.tagger = tagger_a
        self.comic_alpha_2.save()
        self.comic_beta_1.tagger = tagger_b
        self.comic_beta_1.save()

        publisher = Publisher.objects.get(name="ZZ Press")
        url = f"/api/v4/browse/publishers/{publisher.pk}?page=1"
        # Cover view exercises the same ``annotate_order_value`` path
        # for the simple-FK regression this test guards; v4 strips
        # ``groups`` from table-mode responses (tasks/api-v4.md Phase 3)
        # so we'd otherwise need to read from ``rows`` instead.
        self._patch_settings(
            {"viewMode": "cover", "orderBy": "tagger", "orderReverse": False}
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        names = [g.get("name") for g in _v4(response).get("collections", [])]
        assert names == ["Alpha", "Beta"], names

        cache.clear()
        self._patch_settings({"orderReverse": True})
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        names = [g.get("name") for g in _v4(response).get("collections", [])]
        assert names == ["Beta", "Alpha"], names

    def test_primary_sort_by_page_count_on_group_rows(self) -> None:
        """Cumulative ``page_count`` sums across children (matches cover view)."""
        # Alpha's children have page_counts [11, 12] (Sum=23). Beta's
        # only child has page_count=11. ASC → Beta (11) precedes Alpha
        # (23). Cumulative scalars (page_count, size) intentionally
        # use ``Sum`` rather than intersection because the cover-view
        # card already shows the running total — table view matches.
        # Either ``viewMode`` exercises the same Sum aggregate; use
        # cover so the v4 response retains ``groups`` (table-mode strips
        # them — tasks/api-v4.md Phase 3).
        publisher = Publisher.objects.get(name="ZZ Press")
        url = f"/api/v4/browse/publishers/{publisher.pk}?page=1"
        self._patch_settings(
            {"viewMode": "cover", "orderBy": "page_count", "orderReverse": False}
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        names = [g.get("name") for g in _v4(response).get("collections", [])]
        assert names == ["Beta", "Alpha"], names

    def test_primary_sort_at_publishers_root(self) -> None:
        """
        Publishers root (top_collection=p) sorts by aggregated child values.

        Adds a second publisher with one comic, picks a sort key
        whose aggregate differs between the two publishers, and
        verifies the publisher list re-orders accordingly. This is
        the path the user described as "viewing publishers" — rows
        ARE the publishers themselves rather than their children.
        """
        from codex.models.named import Tagger

        # Tag alpha's comics with Alice; beta's comic with Bob; new
        # publisher's comic gets Carol so the order spans three groups.
        tagger_a = Tagger.objects.create(name="Alice")
        tagger_b = Tagger.objects.create(name="Bob")
        tagger_c = Tagger.objects.create(name="Carol")
        self.comic_alpha_1.tagger = tagger_a
        self.comic_alpha_1.save()
        self.comic_alpha_2.tagger = tagger_a
        self.comic_alpha_2.save()
        self.comic_beta_1.tagger = tagger_b
        self.comic_beta_1.save()

        library = Library.objects.first()
        publisher_2 = Publisher.objects.create(name="AA Press")
        imprint_2 = Imprint.objects.create(name="AA Imprint", publisher=publisher_2)
        series_2 = Series.objects.create(
            name="Gamma", imprint=imprint_2, publisher=publisher_2
        )
        volume_2 = Volume.objects.create(
            name="2022", series=series_2, imprint=imprint_2, publisher=publisher_2
        )
        path = TMP_DIR / "g1.cbz"
        path.touch()
        Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name="g1",
            publisher=publisher_2,
            imprint=imprint_2,
            series=series_2,
            volume=volume_2,
            size=200,
            year=2022,
            page_count=20,
            tagger=tagger_c,
        )

        # Browse the root (top_collection=p so each row is a publisher).
        # Use cover view: the assertion below describes Min aggregate
        # semantics (table mode would route through intersection,
        # giving NULL for ZZ Press with mixed taggers). v4 strips
        # ``groups`` from table responses (tasks/api-v4.md Phase 3),
        # so cover is both the assertion-correct mode and the one
        # that keeps ``groups`` in the payload.
        self._patch_settings(
            {
                "viewMode": "cover",
                "topCollection": "publishers",
                "orderBy": "tagger",
                "orderReverse": False,
            }
        )
        response = self.client.get("/api/v4/browse/publishers?page=1")
        assert response.status_code == _HTTP_OK, response.content
        names = [g.get("name") for g in _v4(response).get("collections", [])]
        # Min(comic__tagger__name) per publisher: ZZ Press = Alice (alpha
        # children dominate) tied with Bob → Min = "Alice"; AA Press =
        # "Carol". Asc on those Mins → ZZ Press ("Alice") then AA Press
        # ("Carol").
        assert names == ["ZZ Press", "AA Press"], names

    def test_folder_view_aggregates_through_ancestor_m2m(self) -> None:
        """
        Folder rows aggregate over descendants via ``Comic.folders``.

        Regression: ``Comic.parent_folder`` only points at the
        *direct* parent. Most folders in a real library hold only
        sub-folders, so an FK-based intersection / aggregate returns
        zero comics and every folder row sorts as NULL — the user's
        "Folder view doesn't aggregate years at all" report. The
        ``Comic.folders`` M2M includes every ancestor folder, which
        is the relation the cover-pick logic already uses; the
        intersection / sort path should match.

        Setup:
        - Top folder ``MarvelTop`` containing sub-folder ``MarvelSub``.
          Two comics in ``MarvelSub``, both ``year=2024``.
          → MarvelTop's intersected year (via ``folders``) = 2024.
        - Top folder ``ImageTop`` containing sub-folder ``ImageSub``.
          Two comics in ``ImageSub``, mixed years (2022, 2023).
          → ImageTop's intersected year = NULL.

        Sort desc by year: MarvelTop (2024) before ImageTop (NULL).
        Pre-fix: both top folders have zero direct children, so
        intersection is NULL for both → tie → arbitrary PK order.
        """
        library = Library.objects.first()
        # Folder.presave stats the path so the dirs need to exist.
        marvel_top_path = TMP_DIR / "Marvel"
        marvel_sub_path = marvel_top_path / "Sub"
        image_top_path = TMP_DIR / "Image"
        image_sub_path = image_top_path / "Sub"
        for p in (marvel_sub_path, image_sub_path):
            p.mkdir(parents=True, exist_ok=True)
        marvel_top = Folder.objects.create(
            library=library,
            path=str(marvel_top_path),
            name="MarvelTop",
            parent_folder=None,
        )
        marvel_sub = Folder.objects.create(
            library=library,
            path=str(marvel_sub_path),
            name="MarvelSub",
            parent_folder=marvel_top,
        )
        image_top = Folder.objects.create(
            library=library,
            path=str(image_top_path),
            name="ImageTop",
            parent_folder=None,
        )
        image_sub = Folder.objects.create(
            library=library,
            path=str(image_sub_path),
            name="ImageSub",
            parent_folder=image_top,
        )

        publisher = Publisher.objects.get(name="ZZ Press")
        imprint = Imprint.objects.get(name="ZZ Imprint")
        series_a = Series.objects.get(name="Alpha")
        volume_a = Volume.objects.get(name="2020")

        def _comic_in(sub: Folder, top: Folder, suffix: str, year: int) -> Comic:
            path = TMP_DIR / f"folder-{suffix}.cbz"
            path.touch()
            comic = Comic.objects.create(
                library=library,
                path=path,
                issue_number=1,
                name=suffix,
                publisher=publisher,
                imprint=imprint,
                series=series_a,
                volume=volume_a,
                size=100,
                year=year,
                page_count=20,
                parent_folder=sub,
            )
            comic.folders.set([sub, top])
            return comic

        _comic_in(marvel_sub, marvel_top, "marvel-1", 2024)
        _comic_in(marvel_sub, marvel_top, "marvel-2", 2024)
        _comic_in(image_sub, image_top, "image-1", 2022)
        _comic_in(image_sub, image_top, "image-2", 2023)

        # Browse top-level folders (parent_folder=NULL). Folder view
        # uses the ``folders`` collection; omitted parent_ids means
        # root (top-level folders). View mode stays cover so the
        # response carries ``groups`` (v4 strips ``groups``/``books``
        # from table-mode responses — tasks/api-v4.md Phase 3).
        self._patch_settings(
            {
                "viewMode": "cover",
                "topCollection": "folders",
                "orderBy": "year",
                "orderReverse": True,
            }
        )
        response = self.client.get("/api/v4/browse/folders?page=1")
        assert response.status_code == _HTTP_OK, response.content
        collections = _v4(response).get("collections", [])
        names = [g.get("name") for g in collections]
        # MarvelTop (intersection 2024) sorts before ImageTop (NULL).
        # Both top folders should be present.
        assert "MarvelTop" in names, names
        assert "ImageTop" in names, names
        marvel_idx = names.index("MarvelTop")
        image_idx = names.index("ImageTop")
        assert marvel_idx < image_idx, (
            f"expected MarvelTop before ImageTop in DESC year sort; got {names}"
        )

    def test_year_sort_matches_intersection_display(self) -> None:
        """
        Group-row sort by ``year`` agrees with the displayed intersection.

        Regression: the cell display for a scalar column on a group
        row uses intersection — value shows only when every child
        comic agrees, blank otherwise. The sort key used to be a
        plain ``Min`` aggregate, so a series whose children mostly
        lack a year but one happens to be 2024 sorted as if year=2024
        yet displayed blank. Mirroring intersection in the sort
        keeps display-and-sort consistent: rows whose intersection
        is the same value cluster together; rows with a NULL
        intersection (mixed children) sort to one end.

        Setup:
        - Alpha series: both children year=2020 → intersection 2020.
        - Beta series: only child year=2021 → intersection 2021.
        - Add a third "Mixed" series with two children at different
          years → intersection NULL.

        Sort desc by year: 2021 (Beta), 2020 (Alpha), NULL (Mixed).
        Pre-fix: Mixed sorts as ``MIN(year)``, interleaving with the
        clean groups.
        """
        library = Library.objects.first()
        publisher = Publisher.objects.get(name="ZZ Press")
        imprint = Imprint.objects.get(name="ZZ Imprint")
        series_mixed = Series.objects.create(
            name="Mixed", imprint=imprint, publisher=publisher
        )
        volume_mixed = Volume.objects.create(
            name="2030",
            series=series_mixed,
            imprint=imprint,
            publisher=publisher,
        )
        for issue, year in ((1, 2018), (2, 2024)):
            path = TMP_DIR / f"mixed-{issue}.cbz"
            path.touch()
            Comic.objects.create(
                library=library,
                path=path,
                issue_number=issue,
                name=f"mixed-{issue}",
                publisher=publisher,
                imprint=imprint,
                series=series_mixed,
                volume=volume_mixed,
                size=100 + issue,
                year=year,
                page_count=10 + issue,
            )

        url = f"/api/v4/browse/publishers/{publisher.pk}?page=1"
        self._patch_settings(
            {"viewMode": "table", "orderBy": "year", "orderReverse": True}
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        # Intersection sort is the table-mode behavior under test; v4
        # strips ``groups`` from table responses so read the projection
        # off ``rows`` (tasks/api-v4.md Phase 3).
        names = [r.get("name") for r in _v4(response).get("rows", [])]
        # Beta (2021) before Alpha (2020); Mixed last because its
        # intersection-sort key is NULL.
        assert names == ["Beta", "Alpha", "Mixed"], names

    def test_cover_mode_group_order_value_uses_aggregate(self) -> None:
        """
        Cover view's group order_value is an aggregate, not an intersection.

        Regression: the table-view PR routed collection-row scalar sort
        through ``scalar_intersection_sort_expr`` for every view mode.
        That's correct for table view (sort matches the intersection
        cell display) but blanks the order_value caption beneath
        cover-mode cards for any group whose children disagree on
        the sorted field. Series with mixed years rendered the card
        caption as null; the user reported the same for Publish Date
        across publishers, series, and folders.

        Setup matches ``test_year_sort_matches_intersection_display``
        — Alpha (clean 2020), Beta (single 2021), Mixed (2018 + 2024)
        — but the request uses ``viewMode=cover``. Every collection row
        must come back with a non-null ``orderValue`` so the card
        caption renders.
        """
        library = Library.objects.first()
        publisher = Publisher.objects.get(name="ZZ Press")
        imprint = Imprint.objects.get(name="ZZ Imprint")
        series_mixed = Series.objects.create(
            name="Mixed", imprint=imprint, publisher=publisher
        )
        volume_mixed = Volume.objects.create(
            name="2030",
            series=series_mixed,
            imprint=imprint,
            publisher=publisher,
        )
        for issue, year in ((1, 2018), (2, 2024)):
            path = TMP_DIR / f"mixed-{issue}.cbz"
            path.touch()
            Comic.objects.create(
                library=library,
                path=path,
                issue_number=issue,
                name=f"mixed-{issue}",
                publisher=publisher,
                imprint=imprint,
                series=series_mixed,
                volume=volume_mixed,
                size=100 + issue,
                year=year,
                page_count=10 + issue,
            )

        url = f"/api/v4/browse/publishers/{publisher.pk}?page=1"
        self._patch_settings(
            {"viewMode": "cover", "orderBy": "year", "orderReverse": False}
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        collections = _v4(response).get("collections", [])
        by_name = {g["name"]: g for g in collections}
        # Aggregate (Min year asc): Mixed=2018, Alpha=2020, Beta=2021.
        # None must be null — the user-visible regression was a null
        # caption on Mixed (children disagree). The serializer emits
        # ``order_value`` as a CharField so values come back stringified.
        assert by_name["Alpha"]["orderValue"] == "2020"
        assert by_name["Beta"]["orderValue"] == "2021"
        assert by_name["Mixed"]["orderValue"] == "2018", (
            f"Mixed orderValue should be Min(year)=2018, got {by_name['Mixed']['orderValue']!r}"
        )

    def test_primary_sort_by_year_on_group_rows(self) -> None:
        """Min aggregate over a direct integer field (``year``) sorts correctly."""
        # Alpha has two comics, both year=2020 → Min year = 2020.
        # Beta has one comic, year=2021 → Min year = 2021.
        # Asc → Alpha (2020) first, Beta (2021) second. Both children
        # of each group share their year, so intersection (table mode)
        # and Min aggregate (cover mode) agree; use cover so v4 keeps
        # ``groups`` in the response (tasks/api-v4.md Phase 3).
        publisher = Publisher.objects.get(name="ZZ Press")
        url = f"/api/v4/browse/publishers/{publisher.pk}?page=1"
        self._patch_settings(
            {"viewMode": "cover", "orderBy": "year", "orderReverse": False}
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        names = [g.get("name") for g in _v4(response).get("collections", [])]
        assert names == ["Alpha", "Beta"], names

        cache.clear()
        self._patch_settings({"orderReverse": True})
        response = self.client.get(url)
        names = [g.get("name") for g in _v4(response).get("collections", [])]
        assert names == ["Beta", "Alpha"], names

    def test_primary_sort_with_table_columns_query_params(self) -> None:
        """
        Mirror the request shape the table-view UI actually emits.

        ``columns=`` is included on every page load alongside the
        order-by setting; this exercises the column-annotation
        pipeline's interaction with the order pipeline so a future
        refactor doesn't silently regress sort-with-visible-columns.
        """
        publisher = Publisher.objects.get(name="ZZ Press")
        url = (
            f"/api/v4/browse/publishers/{publisher.pk}"
            "?page=1&columns=cover,name,year,page_count"
        )
        self._patch_settings(
            {"viewMode": "table", "orderBy": "year", "orderReverse": False}
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        # Table-mode column-projection is exactly what this test
        # exercises; v4 strips ``groups`` from table responses so read
        # ``name`` off ``rows`` (tasks/api-v4.md Phase 3).
        names = [r.get("name") for r in _v4(response).get("rows", [])]
        # Year intersection: Alpha=2020 (matched), Beta=2021 (single).
        # ASC → Alpha (2020) before Beta (2021).
        assert names == ["Alpha", "Beta"], names

    def test_multi_column_sort_unsupported_extra_falls_back(self) -> None:
        """
        Reject unsupported-as-extra keys gracefully via ``sort_name`` fallback.

        ``story_arc_number`` / ``search_score`` only resolve in
        narrow contexts. The frontend mirrors this set and refuses
        the shift-click, but the backend still has to be defensive
        against a stored or hand-crafted payload.
        """
        self._patch_settings(
            {
                "viewMode": "table",
                "orderBy": "year",
                "orderReverse": False,
                "orderExtraKeys": [{"key": "story_arc_number", "reverse": False}],
            }
        )
        url = f"/api/v4/browse/series/{Series.objects.get(name='Alpha').pk}?page=1"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content

    def test_multi_column_sort_extras_ignored_in_cover_mode(self) -> None:
        """
        Cover view ignores stored extras.

        With ``view_mode=cover``, the extras tail is intentionally
        skipped — the cover dropdown can't add or edit extras, so
        treating them as authoritative would make cover-grid order
        secretly depend on a setting the user can't see in this
        mode. The tie between the alpha comics now resolves through
        the ``pk`` tiebreaker (alpha_1 is created first).
        """
        self._patch_settings(
            {
                "viewMode": "cover",
                "orderBy": "year",
                "orderReverse": False,
                "orderExtraKeys": [{"key": "issue", "reverse": True}],
            }
        )
        pks = self._browse_comics()
        assert pks == [self.comic_alpha_1.pk, self.comic_alpha_2.pk]

    def test_series_name_ordering_smoke(self) -> None:
        """Sorting comics by series_name (FK path) doesn't error."""
        self._patch_order_by("series_name")
        pks = self._browse_comics()
        assert len(pks) == 2  # noqa: PLR2004

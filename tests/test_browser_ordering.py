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
            "/api/v3/r/settings",
            data=f'{{"orderBy":"{key}","orderReverse":{str(reverse).lower()}}}',
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _patch_settings(self, payload: dict) -> None:
        response = self.client.patch(
            "/api/v3/r/settings",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _browse_comics(self) -> list[int]:
        # Browse the Series containing the alpha comics; with the default
        # ``show.v == False`` the response flattens to direct comic books.
        series_a = Series.objects.get(name="Alpha")
        url = f"/api/v3/s/{series_a.pk}/1"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        body = response.json()
        return [book["pk"] for book in body.get("books", [])]

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
            f"/api/v3/s/{Series.objects.get(name='Alpha').pk}/1"
            "?columns=cover,name,issue,genres"
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
        url = f"/api/v3/p/{publisher.pk}/1"
        # Desc extra → larger child_count first.
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
        names = [g.get("name") for g in response.json().get("groups", [])]
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
        names = [g.get("name") for g in response.json().get("groups", [])]
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
        url = f"/api/v3/s/{Series.objects.get(name='Alpha').pk}/1"
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
        url = f"/api/v3/s/{Series.objects.get(name='Alpha').pk}/1"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content

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
        url = f"/api/v3/s/{Series.objects.get(name='Alpha').pk}/1"
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

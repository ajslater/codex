"""
The series start year, end year and status browser filters.

They filter across the ``Comic.series`` FK rather than a Comic column, and
a blank status is ``""`` rather than NULL, so the "None" status choice has
its own path through availability, choices and filtering.
"""

import json
import shutil
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.choices.browser import DUMMY_NULL_NAME, VUETIFY_NULL_CODE
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_HTTP_BAD_REQUEST: Final = 400
TMP_DIR = tmp_dir("codex.tests.browser_series_filters")
_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"
_STATUS: Final = "Completed"


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


class _SeriesFiltersFixtureTestCase(TestCase):
    """Two series under one publisher: one with every attribute, one bare."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=str(TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.publisher = Publisher.objects.create(name="Pub")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(name="Imp", publisher=self.publisher)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Ser",
            imprint=self.imprint,
            publisher=self.publisher,
            start_year=1963,
            end_year=1996,
            status=_STATUS,
            summary="A friendly neighborhood series.",
        )
        self.other = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Other",
            imprint=self.imprint,
            publisher=self.publisher,
            start_year=2001,
        )
        self._create_comic("C1", self.series)
        self._create_comic("C2", self.other)
        user = User.objects.create_user(
            username="series_filters_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _create_comic(self, name: str, series: Series) -> Comic:
        volume, _ = Volume.objects.get_or_create(
            name=2024, series=series, imprint=self.imprint, publisher=self.publisher
        )
        path = TMP_DIR / f"{name.lower()}.cbz"
        path.touch()
        return Comic.objects.create(
            library=self.library,
            path=path,
            issue_number=1,
            name=name,
            publisher=self.publisher,
            imprint=self.imprint,
            series=series,
            volume=volume,
            size=42,
            year=2024,
            page_count=20,
        )

    def _browse(self, url: str) -> dict:
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)

    def _patch_filters(self, filters: dict):
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"filters": filters}),
            content_type="application/json",
        )
        cache.clear()
        return response

    def _filter(self, filters: dict) -> None:
        response = self._patch_filters(filters)
        assert response.status_code == _HTTP_OK, response.content

    def _availability(self) -> dict:
        cache.clear()
        return self._browse(f"/api/v4/browse/publishers/{self.publisher.pk}/choices")

    def _choices(self, field_name: str) -> list:
        url = f"/api/v4/browse/publishers/{self.publisher.pk}/choices/{field_name}"
        return self._browse(url)["choices"]

    def _series_row_names(self) -> list[str]:
        body = self._browse(f"/api/v4/browse/publishers/{self.publisher.pk}?page=1")
        return sorted(card["name"] for card in body["collections"])


class BrowserSeriesFilterChoicesTestCase(_SeriesFiltersFixtureTestCase):
    """Which filter sub-menus show, and what they offer."""

    def test_available_with_values(self) -> None:
        """Years need one value; status a value plus a blank."""
        body = self._availability()
        assert body["seriesStartYear"] is True, body
        assert body["seriesEndYear"] is True, body
        assert body["seriesStatus"] is True, body

    def test_unavailable_without_values(self) -> None:
        """Blank series offer none of the three."""
        Series.objects.update(start_year=None, end_year=None, status="")
        body = self._availability()
        assert body["seriesStartYear"] is False, body
        assert body["seriesEndYear"] is False, body
        assert body["seriesStatus"] is False, body

    def test_status_with_one_value_and_no_blank(self) -> None:
        """One status and no blank leaves nothing to choose between."""
        Series.objects.update(status=_STATUS)
        body = self._availability()
        assert body["seriesStatus"] is False, body

    def test_year_choices(self) -> None:
        """Year choices are bare values with no null row."""
        assert sorted(self._choices("seriesStartYear")) == [1963, 2001]
        assert self._choices("seriesEndYear") == [1996]

    def test_status_choices(self) -> None:
        """The blank status becomes the "None" row with the int null code."""
        choices = self._choices("seriesStatus")
        assert choices == [
            {"pk": VUETIFY_NULL_CODE, "name": DUMMY_NULL_NAME},
            {"pk": _STATUS, "name": _STATUS},
        ], choices


class BrowserSeriesFilterTestCase(_SeriesFiltersFixtureTestCase):
    """The filters narrow the browse."""

    def test_status_filter(self) -> None:
        """A status selects its series."""
        self._filter({"seriesStatus": [_STATUS]})
        assert self._series_row_names() == ["Ser"]

    def test_status_none_filter(self) -> None:
        """The "None" status selects series with a blank status."""
        self._filter({"seriesStatus": [VUETIFY_NULL_CODE]})
        assert self._series_row_names() == ["Other"]

    def test_start_year_filter(self) -> None:
        """Year filters match any selected year."""
        self._filter({"seriesStartYear": [2001]})
        assert self._series_row_names() == ["Other"]
        self._filter({"seriesStartYear": [1963, 2001]})
        assert self._series_row_names() == ["Other", "Ser"]

    def test_end_year_filter(self) -> None:
        """The end year filter skips series without one."""
        self._filter({"seriesEndYear": [1996]})
        assert self._series_row_names() == ["Ser"]

    def test_filter_on_series_browse(self) -> None:
        """Inside a series the filter applies to its comics."""
        url = f"/api/v4/browse/series/{self.series.pk}?page=1"
        self._filter({"seriesStartYear": [1963]})
        assert [book["name"] for book in self._browse(url)["books"]] == ["C1"]
        self._filter({"seriesStartYear": [2001]})
        assert self._browse(url)["books"] == []

    def test_invalid_status_refused(self) -> None:
        """Only real statuses and the null code validate."""
        response = self._patch_filters({"seriesStatus": ["Finished"]})
        assert response.status_code == _HTTP_BAD_REQUEST, response.content

    def test_status_settings_round_trip(self) -> None:
        """The null code and a status survive saving and reloading."""
        self._filter({"seriesStatus": [VUETIFY_NULL_CODE, _STATUS]})
        body = self._browse(_SETTINGS_URL)
        assert body["filters"]["seriesStatus"] == [VUETIFY_NULL_CODE, _STATUS], body

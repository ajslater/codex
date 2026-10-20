"""The metadata pane carries the series' year range, status and summary."""

import shutil
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

TMP_DIR = tmp_dir("codex.tests.metadata_series_fields")
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_START_YEAR: Final = 1963
_END_YEAR: Final = 1996
_STATUS: Final = "Completed"
_SUMMARY: Final = "A friendly neighborhood series."
_COMIC_SUMMARY: Final = "One issue of it."


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


class MetadataSeriesFieldsTestCase(TestCase):
    """The series attributes reach the metadata payload."""

    @override
    def setUp(self) -> None:
        """Seed one comic in a series with every attribute set."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Ser",
            imprint=imprint,
            publisher=publisher,
            start_year=_START_YEAR,
            end_year=_END_YEAR,
            status=_STATUS,
            summary=_SUMMARY,
        )
        volume = Volume.objects.create(
            name="1963", series=self.series, imprint=imprint, publisher=publisher
        )
        path = TMP_DIR / "c1.cbz"
        path.touch()
        self.comic = Comic.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=library,
            path=path,
            issue_number=1,
            name="C1",
            publisher=publisher,
            imprint=imprint,
            series=self.series,
            volume=volume,
            size=42,
            summary=_COMIC_SUMMARY,
        )
        user = User.objects.create_user(
            username="series_reader", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _get_metadata(self, collection: str, pk: int) -> dict:
        response = self.client.get(f"/api/v4/browse/{collection}/{pk}/metadata")
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)

    def test_comic_metadata_has_series_attrs(self) -> None:
        data = self._get_metadata("comics", self.comic.pk)
        assert data["seriesStartYear"] == _START_YEAR
        assert data["seriesEndYear"] == _END_YEAR
        assert data["seriesStatus"] == _STATUS
        assert data["seriesSummary"] == _SUMMARY

    def test_series_metadata_has_series_attrs(self) -> None:
        """
        A collection's pane reads the attributes through its comics.

        The comics' own summary keeps its key there too, though Series now
        has a summary column of its own.
        """
        data = self._get_metadata("series", self.series.pk)
        assert data["seriesStartYear"] == _START_YEAR
        assert data["seriesEndYear"] == _END_YEAR
        assert data["seriesStatus"] == _STATUS
        assert data["seriesSummary"] == _SUMMARY
        assert data["summary"] == _COMIC_SUMMARY

    def test_unknown_years_are_omitted(self) -> None:
        Series.objects.filter(pk=self.series.pk).update(start_year=None, end_year=None)
        data = self._get_metadata("comics", self.comic.pk)
        assert "seriesStartYear" not in data
        assert "seriesEndYear" not in data

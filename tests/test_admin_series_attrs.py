"""The tag editor saves a series' end year, status and summary to the database."""

import shutil
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

TMP_DIR = tmp_dir("codex.tests.admin_series_attrs")
_URL: Final = "/api/v4/admin/series-attrs"
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_HTTP_BAD_REQUEST: Final = 400
_HTTP_FORBIDDEN: Final = 403
_START_YEAR: Final = 1963
_END_YEAR: Final = 1996
_NEW_END_YEAR: Final = 1998
_SUMMARY: Final = "A friendly neighborhood series."


class AdminSeriesAttrsTestCase(TestCase):
    """POST /admin/series-attrs updates the one series the comics share."""

    @override
    def setUp(self) -> None:
        """Seed two series with one comic each."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=str(TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.publisher = Publisher.objects.create(name="Pub")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(name="Imp", publisher=self.publisher)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series = self._series("Ser", start_year=_START_YEAR, end_year=_END_YEAR)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.other = self._series("Other")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic = self._comic(self.series, "c1.cbz")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.other_comic = self._comic(self.other, "c2.cbz")  # pyright: ignore[reportUninitializedInstanceVariable]
        admin = User.objects.create_user(
            username="series_admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(admin)

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _series(self, name: str, **attrs) -> Series:
        return Series.objects.create(
            name=name, imprint=self.imprint, publisher=self.publisher, **attrs
        )

    def _comic(self, series: Series, filename: str) -> Comic:
        volume = Volume.objects.create(
            name="1963", series=series, imprint=self.imprint, publisher=self.publisher
        )
        path = TMP_DIR / filename
        path.touch()
        return Comic.objects.create(
            library=self.library,
            path=path,
            issue_number=1,
            name=filename,
            publisher=self.publisher,
            imprint=self.imprint,
            series=series,
            volume=volume,
            size=42,
        )

    def _post(self, collection: str, pks, **attrs):
        data = {"collection": collection, "pks": [str(pk) for pk in pks], **attrs}
        return self.client.post(_URL, data, content_type="application/json")

    def test_sets_attrs_on_a_comics_series(self) -> None:
        before = Series.objects.get(pk=self.series.pk).updated_at
        response = self._post(
            "comics",
            [self.comic.pk],
            endYear=_NEW_END_YEAR,
            status="Completed",
            summary=_SUMMARY,
        )
        assert response.status_code == _HTTP_OK, response.content
        series = Series.objects.get(pk=self.series.pk)
        assert series.end_year == _NEW_END_YEAR
        assert series.status == "Completed"
        assert series.summary == _SUMMARY
        assert series.start_year == _START_YEAR
        assert series.updated_at > before
        assert Series.objects.get(pk=self.other.pk).status == ""

    def test_series_collection_targets_its_own_row(self) -> None:
        response = self._post("series", [self.series.pk], status="Hiatus")
        assert response.status_code == _HTTP_OK, response.content
        assert Series.objects.get(pk=self.series.pk).status == "Hiatus"

    def test_only_sent_attrs_change(self) -> None:
        Series.objects.filter(pk=self.series.pk).update(
            status="Ongoing", summary=_SUMMARY
        )
        response = self._post("comics", [self.comic.pk], status="Completed")
        assert response.status_code == _HTTP_OK, response.content
        series = Series.objects.get(pk=self.series.pk)
        assert series.status == "Completed"
        assert series.summary == _SUMMARY
        assert series.end_year == _END_YEAR

    def test_empty_values_clear(self) -> None:
        Series.objects.filter(pk=self.series.pk).update(
            status="Ongoing", summary=_SUMMARY
        )
        response = self._post(
            "comics", [self.comic.pk], endYear=None, status="", summary=""
        )
        assert response.status_code == _HTTP_OK, response.content
        series = Series.objects.get(pk=self.series.pk)
        assert series.end_year is None
        assert series.status == ""
        assert series.summary == ""

    def test_two_series_are_refused(self) -> None:
        response = self._post(
            "comics", [self.comic.pk, self.other_comic.pk], status="Completed"
        )
        assert response.status_code == _HTTP_BAD_REQUEST
        assert Series.objects.get(pk=self.series.pk).status == ""

    def test_nothing_to_save_is_refused(self) -> None:
        response = self._post("comics", [self.comic.pk])
        assert response.status_code == _HTTP_BAD_REQUEST

    def test_unknown_status_is_refused(self) -> None:
        response = self._post("comics", [self.comic.pk], status="Finished")
        assert response.status_code == _HTTP_BAD_REQUEST
        assert Series.objects.get(pk=self.series.pk).status == ""

    def test_out_of_range_year_is_refused(self) -> None:
        response = self._post("comics", [self.comic.pk], endYear=99)
        assert response.status_code == _HTTP_BAD_REQUEST

    def test_non_admin_is_forbidden(self) -> None:
        user = User.objects.create_user(username="reader", password=_TEST_PASSWORD)
        self.client.force_login(user)
        response = self._post("comics", [self.comic.pk], status="Completed")
        assert response.status_code == _HTTP_FORBIDDEN
        assert Series.objects.get(pk=self.series.pk).status == ""

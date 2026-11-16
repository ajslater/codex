"""
Table-view intersections for rows that stand for several pks.

Collection rows group by name, so two same-named series in different
imprints browse as one row under their publisher when imprints are hidden.
That row's cells must describe the comics of every pk in its ``ids``, not
just the one pk the grouped query happens to report.
"""

import json
import shutil
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.models.named import Genre
from codex.startup import init_admin_flags
from codex.views.browser.intersections import _fold_merged_rows
from tests.tmp_dirs import tmp_dir

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"
TMP_DIR = tmp_dir("codex.tests.merged_row_intersections")
_SHARED_YEAR: Final = 2024


class MergedRowIntersectionsTestCase(TestCase):
    """Two "Batman" series under one publisher browse as one merged row."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=str(TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.publisher = Publisher.objects.create(name="DC")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.genres = {  # pyright: ignore[reportUninitializedInstanceVariable]
            name: Genre.objects.create(name=name)
            for name in ("Action", "Comedy", "Drama", "Horror")
        }
        user = User.objects.create_user(username="merged", password=_TEST_PASSWORD)
        self.client = Client()
        self.client.force_login(user)
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"viewMode": "table"}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _series(self, imprint_name: str, series_name: str) -> Series:
        imprint = Imprint.objects.get_or_create(
            name=imprint_name, publisher=self.publisher
        )[0]
        return Series.objects.create(
            name=series_name, publisher=self.publisher, imprint=imprint
        )

    def _comic(self, series: Series, number: int, **fields) -> Comic:
        volume = Volume.objects.get_or_create(
            name=1,
            series=series,
            imprint=series.imprint,
            publisher=self.publisher,
        )[0]
        path = TMP_DIR / f"{series.pk}-{number}.cbz"
        path.touch()
        genres = fields.pop("genres", ())
        comic = Comic.objects.create(
            library=self.library,
            path=path,
            issue_number=number,
            name=f"{series.name} {number}",
            publisher=self.publisher,
            imprint=series.imprint,
            series=series,
            volume=volume,
            size=1,
            **fields,
        )
        comic.genres.set([self.genres[name] for name in genres])
        return comic

    def _rows(self, columns: str) -> dict[str, dict]:
        url = f"/api/v4/browse/publishers/{self.publisher.pk}?page=1&columns={columns}"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return {row["name"]: row for row in response.json()["data"]["rows"]}

    def test_merged_row_covers_every_pk(self):
        """Shared genres, the shared year and summed pages span both series."""
        main = self._series("Main", "Batman")
        black_label = self._series("Black Label", "Batman")
        self._comic(
            main, 1, year=_SHARED_YEAR, page_count=10, genres=("Action", "Drama")
        )
        self._comic(main, 2, year=_SHARED_YEAR, page_count=20, genres=("Drama",))
        self._comic(
            black_label, 1, year=_SHARED_YEAR, page_count=30, genres=("Comedy", "Drama")
        )

        row = self._rows("name,genres,year,page_count")["Batman"]

        assert sorted(row["ids"]) == sorted((main.pk, black_label.pk))
        assert row["genres"] == ["Drama"]
        assert row["year"] == _SHARED_YEAR
        assert row["pageCount"] == 10 + 20 + 30

    def test_merged_row_drops_what_one_pk_lacks(self):
        """A value only one merged series has is not the row's."""
        main = self._series("Main", "Batman")
        black_label = self._series("Black Label", "Batman")
        self._comic(main, 1, year=_SHARED_YEAR, genres=("Action", "Drama"))
        self._comic(black_label, 1, year=_SHARED_YEAR - 1, genres=("Drama",))

        row = self._rows("name,genres,year")["Batman"]

        assert row["genres"] == ["Drama"]
        assert row["year"] is None

    def test_single_pk_row_is_unchanged(self):
        """A row that stands for one series reads only that series."""
        superman = self._series("Main", "Superman")
        self._comic(superman, 1, year=_SHARED_YEAR, genres=("Horror",))
        self._comic(self._series("Main", "Batman"), 1, genres=("Drama",))

        row = self._rows("name,genres,year")["Superman"]

        assert row["ids"] == [superman.pk]
        assert row["genres"] == ["Horror"]
        assert row["year"] == _SHARED_YEAR


class FoldMergedRowsTestCase(SimpleTestCase):
    """The fold skips pks with no visible comics."""

    def test_pk_without_comics_does_not_blank_the_row(self):
        per_pk = {
            1: {"year": 2024, "page_count": 5, "genres": ["Drama"]},
            2: {"year": None, "page_count": None, "genres": []},
        }
        folded = _fold_merged_rows(
            {1: (1, 2)},
            per_pk,
            {1: 3, 2: 0},
            [("year", "year")],
            [("page_count", "page_count")],
        )
        assert folded == {1: {"year": 2024, "page_count": 5, "genres": ["Drama"]}}

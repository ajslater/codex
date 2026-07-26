"""
The ``reprints`` browser table column and filter.

``Reprint`` is the only tag model without a ``name`` column — the label
composes from four — so both the table cell (Comic rows and collection-row
intersections) and the filter drawer need their own label paths. These
tests pin all of them to :meth:`Reprint.compose_name`'s output.
"""

import json
import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.choices.browser import DUMMY_NULL_NAME, VUETIFY_NULL_CODE
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.models.named import Reprint
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
TMP_DIR = Path("/tmp/codex.tests.browser_reprints_column")  # noqa: S108
_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


class _ReprintsFixtureTestCase(TestCase):
    """One publisher / imprint / series / volume and one comic to tag."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=str(TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.publisher = Publisher.objects.create(name="Pub")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(name="Imp", publisher=self.publisher)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series = self._create_series("Ser")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic = self._create_comic("C1", 1)  # pyright: ignore[reportUninitializedInstanceVariable]
        user = User.objects.create_user(
            username="reprints_column_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _create_series(self, name: str) -> Series:
        return Series.objects.create(
            name=name, imprint=self.imprint, publisher=self.publisher
        )

    def _create_comic(
        self, name: str, issue_number: int, series: Series | None = None
    ) -> Comic:
        series = series or self.series
        volume, _ = Volume.objects.get_or_create(
            name=2024, series=series, imprint=self.imprint, publisher=self.publisher
        )
        path = TMP_DIR / f"{name.lower()}.cbz"
        path.touch()
        return Comic.objects.create(
            library=self.library,
            path=path,
            issue_number=issue_number,
            name=name,
            publisher=self.publisher,
            imprint=self.imprint,
            series=series,
            volume=volume,
            size=42 + issue_number,
            year=2024,
            page_count=20,
        )

    def _set_view_mode_table(self) -> None:
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"viewMode": "table"}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _browse(self, url: str) -> dict:
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)

    def _browse_comics(self, columns: str = "cover,name,reprints") -> dict:
        return self._browse(
            f"/api/v4/browse/series/{self.series.pk}?page=1&columns={columns}"
        )

    def _browse_series_rows(self, columns: str = "cover,name,reprints") -> dict:
        return self._browse(
            f"/api/v4/browse/publishers/{self.publisher.pk}?page=1&columns={columns}"
        )


class BrowserReprintsColumnTestCase(_ReprintsFixtureTestCase):
    """Table-cell display and sort for the composed alternate-series label."""

    def test_comic_row_composes_every_part(self) -> None:
        """The SQL expression renders the same label as ``Reprint.compose_name``."""
        reprints = (
            Reprint.objects.create(series_name="Kapitän Wissenschaft"),
            Reprint.objects.create(series_name="Capitan Sciencia", volume_number=1),
            Reprint.objects.create(series_name="Yearly", volume_number=1999),
            Reprint.objects.create(
                series_name="Full", volume_number=3, issue="2a", language="es"
            ),
        )
        self.comic.reprints.set(reprints)

        self._set_view_mode_table()
        row = self._browse_comics()["rows"][0]
        assert sorted(row["reprints"]) == sorted(
            reprint.name for reprint in reprints
        ), row
        # Spell the expectations out so a change to either the SQL or
        # the Python composer fails loudly instead of agreeing wrongly.
        # The aggregate sorts its own elements — identical reprint sets
        # must render identical JSON for the M2M sort to cluster them.
        assert row["reprints"] == [
            "Capitan Sciencia v1",
            "Full v3 #2a (es)",
            "Kapitän Wissenschaft",
            "Yearly (1999)",
        ]

    def test_collection_row_shows_only_shared_reprints(self) -> None:
        """A series row intersects its children's reprints."""
        shared = Reprint.objects.create(series_name="Shared", language="de")
        lonely = Reprint.objects.create(series_name="Lonely")
        self.comic.reprints.set((shared, lonely))
        sibling = self._create_comic("C2", 2)
        sibling.reprints.set((shared,))

        self._set_view_mode_table()
        row = self._browse_series_rows()["rows"][0]
        assert row["reprints"] == ["Shared (de)"], row

    def test_collection_row_without_reprints_is_empty(self) -> None:
        """Collections whose children carry no reprints render an empty cell."""
        self._set_view_mode_table()
        row = self._browse_series_rows()["rows"][0]
        assert row["reprints"] == [], row

    def test_collection_row_sort_by_reprints(self) -> None:
        """Sorting collection rows by the column uses its intersection SQL."""
        self.comic.reprints.add(
            Reprint.objects.create(series_name="Zulu", volume_number=2)
        )
        # "Zzz" has no reprints, so ascending by the column puts it
        # first — the opposite of the ``sort_name`` order the sort
        # falls back to when the intersection SQL isn't wired.
        self._create_comic("C2", 1, series=self._create_series("Zzz"))

        self._set_view_mode_table()
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"orderBy": "reprints", "orderReverse": False}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        rows = self._browse_series_rows()["rows"]
        assert [(row["name"], row["reprints"]) for row in rows] == [
            ("Zzz", []),
            ("Ser", ["Zulu v2"]),
        ], rows


class BrowserReprintsFilterTestCase(_ReprintsFixtureTestCase):
    """The filter drawer's choices and the resulting narrowing."""

    def test_choices_compose_labels(self) -> None:
        """The choices endpoint labels reprints like the metadata panel does."""
        reprint = Reprint.objects.create(
            series_name="Kapitän Wissenschaft", language="de"
        )
        self.comic.reprints.add(reprint)
        # A reprint-less sibling makes the view prepend the null
        # sentinel, which already carries a name of its own.
        self._create_comic("C2", 2)

        body = self._browse(f"/api/v4/browse/series/{self.series.pk}/choices/reprints")
        choices = {choice["pk"]: choice["name"] for choice in body["choices"]}
        assert choices[reprint.pk] == "Kapitän Wissenschaft (de)", choices
        assert choices[VUETIFY_NULL_CODE] == DUMMY_NULL_NAME, choices

    def test_choices_availability(self) -> None:
        """``reprints`` only offers a sub-menu once a value and a null exist."""
        body = self._browse(f"/api/v4/browse/series/{self.series.pk}/choices")
        assert body["reprints"] is False, body

        self.comic.reprints.add(Reprint.objects.create(series_name="Alt"))
        self._create_comic("C2", 2)
        cache.clear()
        body = self._browse(f"/api/v4/browse/series/{self.series.pk}/choices")
        assert body["reprints"] is True, body

    def test_filter_narrows_to_tagged_comics(self) -> None:
        """Selecting a reprint pk filters the browse to comics carrying it."""
        reprint = Reprint.objects.create(series_name="Alt", volume_number=1)
        self.comic.reprints.add(reprint)
        self._create_comic("C2", 2)

        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"filters": {"reprints": [reprint.pk]}}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        cache.clear()
        body = self._browse(f"/api/v4/browse/series/{self.series.pk}?page=1")
        names = [book["name"] for book in body["books"]]
        assert names == ["C1"], body

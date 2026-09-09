"""
The metadata pane serves reprint series names as ready-to-render chips.

``Reprint.name`` is a property composed from four columns, so the
metadata endpoint has to hydrate all of them plus the optional
identifier in one query. Without the ``M2M_QUERY_OPTIMIZERS`` entry the
default ``only=("name", "identifier")`` raises FieldDoesNotExist.
"""

import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from codex.models import (
    Comic,
    Imprint,
    Library,
    Publisher,
    Reprint,
    Series,
    Volume,
)
from codex.models.identifier import Identifier, IdentifierSource, IdentifierType
from codex.startup import init_admin_flags

TMP_DIR = Path("/tmp/codex.tests.metadata_reprints")  # noqa: S108
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_REPRINT_TABLE: Final = 'FROM "codex_reprint"'
_REPRINT_COUNT: Final = 3


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


class MetadataReprintsTestCase(TestCase):
    """The reprints payload shape and its query cost."""

    @override
    def setUp(self) -> None:
        """Seed one comic with three reprints of varying completeness."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Ser", imprint=imprint, publisher=publisher
        )
        volume = Volume.objects.create(
            name="2024", series=self.series, imprint=imprint, publisher=publisher
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
        )
        source = IdentifierSource.objects.create(name="metron")
        identifier = Identifier.objects.create(
            source=source,
            id_type=IdentifierType.REPRINT.value,
            key="12345",
            url="https://metron.cloud/series/12345",
        )
        self.comic.reprints.set(
            [
                Reprint.objects.create(series_name="Kapitän Wissenschaft"),
                Reprint.objects.create(
                    series_name="Capitan Sciencia", volume_number=1, language="es"
                ),
                Reprint.objects.create(
                    series_name="Captain Science",
                    issue="3",
                    identifier=identifier,
                ),
            ]
        )

        user = User.objects.create_user(
            username="reprint_reader", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _get_metadata(self, url: str = ""):
        url = url or f"/api/v4/browse/comics/{self.comic.pk}/metadata"
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response), ctx.captured_queries

    def test_reprint_names_compose_present_parts(self) -> None:
        """Each chip name composes only the columns the reprint carries."""
        data, _ = self._get_metadata()
        names = sorted(reprint["name"] for reprint in data["reprints"])
        assert names == [
            "Capitan Sciencia v1 (es)",
            "Captain Science #3",
            "Kapitän Wissenschaft",
        ], names

    def test_reprint_columns_ship_beside_the_composed_name(self) -> None:
        """The tag editor seeds its rows from the parts, not the label."""
        data, _ = self._get_metadata()
        parts = {
            reprint["seriesName"]: (
                reprint["volumeNumber"],
                reprint["issue"],
                reprint["language"],
            )
            for reprint in data["reprints"]
        }
        assert parts == {
            "Kapitän Wissenschaft": (None, "", ""),
            "Capitan Sciencia": (1, "", "es"),
            "Captain Science": (None, "3", ""),
        }, parts

    def test_reprint_identifier_url_ships_when_set(self) -> None:
        """The identifier url rides along for the chip's external link."""
        data, _ = self._get_metadata()
        urls = {reprint["name"]: reprint.get("url", "") for reprint in data["reprints"]}
        assert urls["Captain Science #3"] == "https://metron.cloud/series/12345"
        assert not urls["Kapitän Wissenschaft"]

    def test_collection_selection_serves_the_intersection(self) -> None:
        """Collections take the plain-attribute branch, not the prefetch cache."""
        url = f"/api/v4/browse/series/{self.series.pk}/metadata"
        data, _ = self._get_metadata(url)
        assert len(data["reprints"]) == _REPRINT_COUNT, data["reprints"]

    def test_reprints_hydrate_in_one_query(self) -> None:
        """No per-reprint query for the deferred columns or the identifier."""
        _, queries = self._get_metadata()
        reprint_queries = [q for q in queries if _REPRINT_TABLE in q["sql"]]
        assert len(reprint_queries) == 1, reprint_queries

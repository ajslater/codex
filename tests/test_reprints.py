"""
Reprint series names, from the archive to the browser and back out.

``tests/files/comicbox-2-example.cbz`` carries two MetronInfo alternate
names, one of which supplies only a series ``sort_name``. Importing it
is the only place the whole chain — comicbox whitelist, four-column key
flattening, m2m link, display label and the nightly orphan sweep —
meets end to end. The search half of the chain lives in
``tests/test_search_alternate_series.py``.
"""

from http import HTTPStatus
from multiprocessing import Event as ProcessEvent
from threading import Lock
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.read.many_to_many import (
    AggregateManyToManyMetadataImporter,
)
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.models import Comic, Reprint, Series, Volume
from tests.importer.test_basic import PATH, BaseTestImporter, run_full_import

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
# The fixture's two alternate names, as ``Reprint`` natural keys.
_FIXTURE_KEYS: Final = {
    ("Capitan Sciencia", 1, "", "es"),
    ("Kapitän Wissenschaft", None, "", "de"),
}
_SORT_NAME_ONLY: Final = "Capitan Sciencia"


def _reprint_keys() -> set[tuple]:
    """Every Reprint row in the database, as natural-key tuples."""
    return set(
        Reprint.objects.values_list("series_name", "volume_number", "issue", "language")
    )


def _make_janitor() -> Janitor:
    """Build a Janitor detached from the librarian's thread graph."""
    return Janitor(logger, LIBRARIAN_QUEUE, Lock(), ProcessEvent())


class ReprintImportTestCase(BaseTestImporter):
    """Import the example fixture and follow its reprints downstream."""

    @override
    def setUp(self) -> None:
        super().setUp()
        run_full_import(self.importer)
        self.comic = Comic.objects.get(path=PATH)

    def test_import_creates_rows_keyed_on_all_four_columns(self) -> None:
        """Every part comicbox supplied lands in its own column."""
        assert _reprint_keys() == _FIXTURE_KEYS
        linked = self.comic.reprints.values_list(
            "series_name", "volume_number", "issue", "language"
        )
        assert set(linked) == _FIXTURE_KEYS

    def test_sort_name_stands_in_for_a_missing_series_name(self) -> None:
        """
        One AlternativeNames entry carries no ``series.name`` at all.

        It must still import, and — the reason ``Reprint`` denormalizes
        instead of reusing Series/Volume — it must not become a
        browsable collection row.
        """
        assert Reprint.objects.filter(series_name=_SORT_NAME_ONLY).exists()
        assert not Series.objects.filter(name=_SORT_NAME_ONLY).exists()
        assert not Volume.objects.filter(series__name=_SORT_NAME_ONLY).exists()

    def test_metadata_endpoint_serves_imported_reprints(self) -> None:
        """Imported rows reach the panel as composed display labels."""
        user = User.objects.create_user(
            username="reprint_round_trip", password=_TEST_PASSWORD
        )
        client = Client()
        client.force_login(user)
        response = client.get(f"/api/v4/browse/comics/{self.comic.pk}/metadata")
        assert response.status_code == HTTPStatus.OK, response.content
        names = sorted(
            reprint["name"] for reprint in response.json()["data"]["reprints"]
        )
        assert names == ["Capitan Sciencia v1 (es)", "Kapitän Wissenschaft (de)"]

    def test_cleanup_fks_keeps_linked_reprints(self) -> None:
        """The nightly sweep leaves reprints a comic still points at."""
        _make_janitor().cleanup_fks()
        assert _reprint_keys() == _FIXTURE_KEYS

    def test_cleanup_fks_deletes_orphaned_reprints(self) -> None:
        """Deleting the last comic that referenced them sweeps them away."""
        self.comic.delete()
        _make_janitor().cleanup_fks()
        assert not Reprint.objects.exists()


class ReprintKeyFlatteningTestCase(SimpleTestCase):
    """The nested comicbox tree collapses to the four-column key."""

    @staticmethod
    def _clean(reprint: dict) -> tuple | None:
        return AggregateManyToManyMetadataImporter._clean_reprint_key(reprint)  # noqa: SLF001

    def test_series_name_wins_over_sort_name(self) -> None:
        """``sort_name`` only fills in for a reprint that has no name."""
        key = self._clean({"series": {"name": "Real", "sort_name": "Sorted"}})
        assert key == ("Real", None, "", "")

    def test_every_part_flattens_to_its_column(self) -> None:
        """Volume number, issue and language come out of their subtrees."""
        key = self._clean(
            {
                "series": {"name": "Kapitän Wissenschaft"},
                "volume": {"number": 2},
                "issue": "3",
                "language": "de",
            }
        )
        assert key == ("Kapitän Wissenschaft", 2, "3", "de")

    def test_reprint_without_any_series_name_is_dropped(self) -> None:
        """A reprint naming nothing can't key a row, so it never becomes one."""
        assert self._clean({"volume": {"number": 1}, "language": "de"}) is None
        assert self._clean({"series": {}}) is None
        assert self._clean({"series": {"name": "   "}}) is None

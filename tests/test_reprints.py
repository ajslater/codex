"""
Reprint series names, from the archive to the browser and back out.

``tests/files/comicbox-2-example.cbz`` carries two reprints, one of
which names an edition without spelling out its series. Importing it is
the only place the whole chain — comicbox whitelist, four-column key
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
# The fixture's two reprints, as ``Reprint`` natural keys.
_FIXTURE_KEYS: Final = {
    ("Capitan Sciencia", 1, "", "es"),
    ("Kapitän Wissenschaft", None, "", "de"),
}
# The one the file names without spelling out a series.
_NAME_ONLY: Final = "Capitan Sciencia"


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

    def test_a_reprint_named_without_a_series_still_imports(self) -> None:
        """
        One reprint states only the name the file gave it.

        It must still import, and — the reason ``Reprint`` denormalizes
        instead of reusing Series/Volume — it must not become a
        browsable collection row.
        """
        assert Reprint.objects.filter(series_name=_NAME_ONLY).exists()
        assert not Series.objects.filter(name=_NAME_ONLY).exists()
        assert not Volume.objects.filter(series__name=_NAME_ONLY).exists()

    def test_the_series_other_name_is_flagged_as_one(self) -> None:
        """
        Both lists land in one table, and the row remembers which it came from.

        Comicbox 5 files a series' localized and variant titles under the
        series rather than among the reprints. Codex keeps one table for
        both, so the flag is what a write consults to put each row back
        into the list it belongs to.
        """
        alternative_name = Reprint.objects.get(series_name="Kapitän Wissenschaft")
        assert alternative_name.alternative_name is True
        reprint = Reprint.objects.get(series_name=_NAME_ONLY)
        assert reprint.alternative_name is False

    def test_an_alternative_names_identifier_is_the_series_it_names(self) -> None:
        """
        Where the id sits no longer implies what it identifies.

        An id on one of the series' other names is a series id, so codex
        states the type when folding the name in among the reprints and
        the link it builds points at the series rather than nowhere.
        """
        alternative_name = Reprint.objects.get(series_name="Kapitän Wissenschaft")
        identifier = alternative_name.identifier
        assert identifier is not None
        assert identifier.key == "4242"
        assert identifier.url == "https://metron.cloud/series/4242"

    def test_a_reprints_identifier_links_to_the_issue_it_reprints(self) -> None:
        """
        A reprint's id names an issue, not a "reprint".

        No database publishes a page for a reprint, so reading the id's
        type off the table it hangs on built no link at all. The row is
        another edition of this book and its id names that edition.
        """
        reprint = Reprint.objects.get(series_name=_NAME_ONLY)
        identifier = reprint.identifier
        assert identifier is not None
        assert identifier.url == "https://metron.cloud/issue/4444"

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

    def test_series_name_wins_over_the_reprints_own_name(self) -> None:
        """The parsed series is the better key when there is one."""
        key = self._clean({"name": "Real (2020) #1", "series": {"name": "Real"}})
        assert key == ("Real", None, "", "")

    def test_the_reprints_own_name_stands_in_for_a_missing_series(self) -> None:
        """
        A reprint keeps the name the file gave it.

        Comicbox parses a series out of that name when it can, but a file
        is free to name an edition without spelling one out, and that
        still has to key a row rather than vanish.
        """
        key = self._clean({"name": "Capitan Sciencia"})
        assert key == ("Capitan Sciencia", None, "", "")

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

    def test_reprint_without_any_name_is_dropped(self) -> None:
        """A reprint naming nothing can't key a row, so it never becomes one."""
        assert self._clean({"volume": {"number": 1}, "language": "de"}) is None
        assert self._clean({"series": {}}) is None
        assert self._clean({"series": {"name": "   "}}) is None
        assert self._clean({"name": ""}) is None

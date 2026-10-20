"""
Comics of one series combine their series attributes in an import batch.

Every comic proposes its own values for its series row. Within a batch
they merge per attribute: the earliest start year, the latest end year,
the largest count and the first comic's status and text. Against the
stored row a
later batch's values win and missing ones leave it alone.
"""

import shutil
import zipfile
from pathlib import Path
from threading import Event, Lock
from typing import Final, override

from django.core.cache import cache
from django.test import TestCase
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.const import (
    CREATE_FKS,
    EXTRACTED,
    FIS,
    UPDATE_FKS,
)
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.models import Series, Volume
from codex.models.library import Library
from codex.startup import codex_init
from tests.tmp_dirs import tmp_dir

TMP_DIR: Final = tmp_dir(Path(__file__).stem)
_VOLUME_NUMBER: Final = 1963
_EARLY: Final = 1963
_MIDDLE: Final = 1970
_LATE: Final = 1996
_FEW: Final = 3
_MANY: Final = 7
_SUMMARY_B: Final = "The second comic's series summary."
_SUMMARY_C: Final = "The third comic's series summary."
_ONGOING: Final = "Ongoing"
_COMPLETED: Final = "Completed"


_ARCHIVE_YAML: Final = f"""comicbox:
  publisher:
    name: P
  series:
    name: S
    start_year: {_EARLY}
    end_year: {_LATE}
    status: completed
    summary: {_SUMMARY_B}
"""


def _md(series: dict | None = None, volume: dict | None = None) -> dict:
    """Comicbox metadata for one comic of series S."""
    return {
        "publisher": {"name": "P"},
        "series": {"name": "S", **(series or {})},
        "volume": {"number": _VOLUME_NUMBER, **(volume or {})},
    }


class TestSeriesAttrs(TestCase):
    """Series attributes merge in a batch and update the stored row."""

    @override
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cache.clear()
        codex_init()
        TMP_DIR.mkdir(exist_ok=True, parents=True)

    @override
    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(TMP_DIR, ignore_errors=True)
        finally:
            super().tearDownClass()

    @override
    def setUp(self):
        cache.clear()
        self.library = Library.objects.create(path=TMP_DIR)  # pyright: ignore[reportUninitializedInstanceVariable]

    def _importer(self, paths) -> ComicImporter:
        task = ImportTask(library_id=self.library.pk, files_modified=frozenset(paths))
        return ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())

    @staticmethod
    def _create_collections(importer: ComicImporter) -> None:
        importer.metadata[CREATE_FKS] = {}
        importer.metadata[UPDATE_FKS] = {}
        importer.query_all_missing_models()
        importer.create_all_fks()
        importer.update_all_fks()

    def _import(self, *mds: dict) -> None:
        """Aggregate, query and create the collections for one batch."""
        paths = {str(TMP_DIR / f"c{index}.cbz"): md for index, md in enumerate(mds)}
        importer = self._importer(paths)
        importer.metadata[FIS] = {}
        importer.metadata[EXTRACTED] = paths
        importer.aggregate_metadata()
        self._create_collections(importer)

    def test_archive_series_attrs(self) -> None:
        """The attributes come through from an archive's comicbox metadata."""
        path = TMP_DIR / "archive.cbz"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("comicbox.yaml", _ARCHIVE_YAML)
            zf.writestr("page1.jpg", b"\xff\xd8\xff\xe0not-a-real-jpeg")
        importer = self._importer({str(path)})
        importer.read()
        self._create_collections(importer)

        series = Series.objects.get(name="S")
        assert series.start_year == _EARLY
        assert series.end_year == _LATE
        assert series.status == _COMPLETED
        assert series.summary == _SUMMARY_B

    def test_batch_merges_series_attrs(self) -> None:
        """Earliest start, latest end, largest count, first status and text."""
        self._import(
            _md({"start_year": _MIDDLE, "volume_count": _MANY}),
            _md(
                {
                    "start_year": _EARLY,
                    "end_year": _LATE,
                    "status": _ONGOING,
                    "summary": _SUMMARY_B,
                },
                {"issue_count": _MANY},
            ),
            _md(
                {
                    "end_year": _MIDDLE,
                    "volume_count": _FEW,
                    "status": _COMPLETED,
                    "summary": _SUMMARY_C,
                },
                {"issue_count": _FEW},
            ),
        )

        series = Series.objects.get(name="S")
        assert series.start_year == _EARLY
        assert series.end_year == _LATE
        assert series.volume_count == _MANY
        assert series.status == _ONGOING
        assert series.summary == _SUMMARY_B
        assert Volume.objects.get(series=series).issue_count == _MANY

    def test_missing_attrs_create_empty(self) -> None:
        """A series with no attributes gets nulls and empty text."""
        self._import(_md())

        series = Series.objects.get(name="S")
        assert series.start_year is None
        assert series.end_year is None
        assert series.status == ""
        assert series.summary == ""

    def test_later_batch_updates_stored_series(self) -> None:
        """A later batch's values replace stored ones; missing ones don't."""
        self._import(
            _md(
                {
                    "start_year": _EARLY,
                    "end_year": _MIDDLE,
                    "status": _ONGOING,
                    "summary": _SUMMARY_B,
                }
            )
        )
        self._import(_md({"end_year": _LATE, "status": _COMPLETED}))

        series = Series.objects.get(name="S")
        assert series.start_year == _EARLY
        assert series.end_year == _LATE
        assert series.status == _COMPLETED
        assert series.summary == _SUMMARY_B

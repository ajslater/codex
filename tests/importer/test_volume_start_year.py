"""
Each volume keeps its own start year (issue 1053).

comicbox's series is one volume run, so a comic's ``series.start_year`` is
its volume's. The series row still folds them, earliest in a batch.
"""

import shutil
import zipfile
from pathlib import Path
from threading import Event, Lock
from typing import Final, override

from django.core.cache import cache
from django.test import TestCase
from loguru import logger

from codex.librarian.scribe.importer.const import CREATE_FKS, EXTRACTED, FIS, UPDATE_FKS
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.readinglists.tasks import ReadingListRematchTask
from codex.librarian.scribe.readinglists.volume_years import (
    queue_volume_start_years,
    volume_year_comics,
)
from codex.librarian.scribe.tasks import ForceUpdateComicsTask
from codex.models import Comic, Series, Timestamp, Volume
from codex.models.library import Library
from codex.startup import codex_init
from tests.importer.test_basic import run_full_import
from tests.tmp_dirs import tmp_dir

TMP_DIR: Final = tmp_dir(Path(__file__).stem)
_KEY: Final = Timestamp.Choices.VOLUME_START_YEARS.value
_GOLDEN: Final = 1940


class _Queue:
    def __init__(self) -> None:
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


def _md(volume: int | None, start_year: int | None) -> dict:
    series: dict = {"name": "Batman"}
    if start_year:
        series["start_year"] = start_year
    md: dict = {"publisher": {"name": "DC"}, "series": series}
    if volume is not None:
        md["volume"] = {"number": volume}
    return md


def _yaml(volume: int, start_year: int, number: int) -> str:
    return f"""comicbox:
  publisher:
    name: DC
  series:
    name: Batman
    start_year: {start_year}
  volume:
    number: {volume}
  issue:
    name: "{number}"
"""


def _years() -> dict[int | None, int | None]:
    return dict(Volume.objects.values_list("name", "start_year"))


class _Base(TestCase):
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

    def importer(self, paths, queue=None, **kwargs) -> ComicImporter:
        task = ImportTask(
            library_id=self.library.pk, files_modified=frozenset(paths), **kwargs
        )
        return ComicImporter(task, logger, queue or _Queue(), Lock(), Event())  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]


class VolumeStartYearTests(_Base):
    """The importer gives each volume its comics' start year."""

    def _import(self, *mds: dict) -> None:
        paths = {str(TMP_DIR / f"c{index}.cbz"): md for index, md in enumerate(mds)}
        importer = self.importer(paths)
        importer.metadata[FIS] = {}
        importer.metadata[EXTRACTED] = paths
        importer.aggregate_metadata()
        importer.metadata[CREATE_FKS] = {}
        importer.metadata[UPDATE_FKS] = {}
        importer.query_all_missing_models()
        importer.create_all_fks()
        importer.update_all_fks()

    def test_one_batch(self) -> None:
        """Two volumes in one batch keep two years; the series the earliest."""
        self._import(_md(2011, 2011), _md(1940, 1940), _md(2011, 2011))
        assert _years() == {1940: 1940, 2011: 2011}
        assert Series.objects.get().start_year == _GOLDEN

    def test_across_batches(self) -> None:
        """A later batch's volume gets its own year, the first keeps its."""
        self._import(_md(1940, 1940))
        self._import(_md(2016, 2016))
        assert _years() == {1940: 1940, 2016: 2016}

    def test_no_volume_tag(self) -> None:
        """A comic with no volume gives its year to the null volume."""
        self._import(_md(None, 2016))
        assert _years() == {None: 2016}


class ForcedReadTests(_Base):
    """The one-time re-read after migration 0062 learns each volume's year."""

    @override
    def setUp(self):
        super().setUp()
        self.paths = []  # pyright: ignore[reportUninitializedInstanceVariable]
        for index, (volume, year) in enumerate(((1940, 1940), (2, 2011), (2, 2011))):
            path = TMP_DIR / f"b{index}.cbz"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("comicbox.yaml", _yaml(volume, year, index + 1))
                zf.writestr("page1.jpg", b"\xff\xd8\xff\xe0not-a-real-jpeg")
            self.paths.append(str(path))
        run_full_import(self.importer(self.paths))
        # As migration 0062 leaves a series with several volumes.
        Volume.objects.update(start_year=None)
        Timestamp.objects.filter(key=_KEY).update(value="pending")

    def test_startup_queues_one_comic_per_volume_once(self) -> None:
        comics = volume_year_comics()
        assert len(comics) == Volume.objects.count()
        first_of_two = Comic.objects.filter(volume__name=2).order_by("pk").first()
        assert first_of_two
        assert first_of_two.pk in comics

        queue = _Queue()
        queue_volume_start_years(queue)
        force, rematch = queue.items
        assert isinstance(force, ForceUpdateComicsTask)
        assert force.comic_pks == comics
        assert isinstance(rematch, ReadingListRematchTask)
        assert not rematch.list_pks

        again = _Queue()
        queue_volume_start_years(again)
        assert again.items == []

    def test_the_forced_read_sets_years_and_queues_a_rematch(self) -> None:
        comics = volume_year_comics()
        paths = Comic.objects.filter(pk__in=comics).values_list("path", flat=True)
        queue = _Queue()
        importer = self.importer(
            paths, queue, force_import_metadata=True, check_metadata_mtime=False
        )
        run_full_import(importer)
        assert _years() == {1940: 1940, 2: 2011}
        assert any(isinstance(task, ReadingListRematchTask) for task in queue.items)

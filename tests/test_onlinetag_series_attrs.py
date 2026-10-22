"""
Online tagging keeps the series attributes no written format can hold.

A Metron match brings the series' end year, status and summary, and
ComicInfo has no start year either. The tag write can't put them in the
file, so they ride on the re-read and the importer applies them to the
series the comic lands on. Here the match also names a new publisher and
series, which moves the comic off its filename-derived series row: the
values have to reach the new row, not the one the comic left.
"""

import shutil
import threading
import zipfile
from pathlib import Path
from threading import Event, Lock
from types import SimpleNamespace
from typing import Any, Final, override
from unittest.mock import MagicMock

from comicbox.enums.comicbox import SeriesStatusEnum
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.onlinetag.tag_pass_runner import TagPassRunner
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.tag_writer import TagWriter
from codex.librarian.scribe.tagwrite_series_attrs import patch_series_attrs
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import Comic, Library, Series
from codex.startup import codex_init
from tests.importer.test_basic import run_full_import
from tests.onlinetag_session_fakes import FakeQueue, double
from tests.tmp_dirs import tmp_dir

_TMP_DIR: Final = tmp_dir("codex.tests.onlinetag.series_attrs")
_FILENAME_SERIES: Final = "Spidey"
_SERIES: Final = "The Amazing Spider-Man"
_START_YEAR: Final = 1963
_END_YEAR: Final = 1998
_STATUS: Final = "Completed"
_SUMMARY: Final = "The first Spider-Man series."
#: The tags a Metron match hands back, trimmed to what this test reads.
_MATCH_TAGS: Final = {
    "publisher": {"name": "Marvel"},
    "series": {
        "name": _SERIES,
        "start_year": _START_YEAR,
        "end_year": _END_YEAR,
        "status": _STATUS,
        "summary": _SUMMARY,
    },
    "issue": {"number": "1"},
}


class _NoopStatusController:
    def start(self, _status, **_kwargs) -> None:
        pass

    def update(self, _status, **_kwargs) -> None:
        pass

    def finish(self, _status, **_kwargs) -> None:
        pass


class _MatchedSession:
    """Matches every comic to ``_MATCH_TAGS``."""

    def tag_many(self, paths):
        for path in paths:
            yield SimpleNamespace(
                path=path, matched=True, tags=_MATCH_TAGS, error=None, cancelled=False
            )


def _untagged_cbz(path: Path) -> None:
    """Build an archive with no metadata, so its series comes from its name."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("page1.jpg", b"\xff\xd8\xff\xe0not-a-real-jpeg")


def _make_writer(queue: FakeQueue) -> TagWriter:
    """Build a TagWriter without the threading machinery."""
    writer = TagWriter.__new__(TagWriter)
    writer.log = double(logger)
    writer.librarian_queue = double(queue)
    writer.status_controller = double(MagicMock())
    writer.abort_event = threading.Event()
    return writer


def _queued(queue: FakeQueue, task_type: type) -> list[Any]:
    return [item for item in queue.items if isinstance(item, task_type)]


class PatchSeriesAttrsTestCase(SimpleTestCase):
    """Only non-empty attributes leave the patch, status as its choice value."""

    def test_picks_the_attrs(self) -> None:
        assert patch_series_attrs(_MATCH_TAGS) == {
            "start_year": _START_YEAR,
            "end_year": _END_YEAR,
            "status": _STATUS,
            "summary": _SUMMARY,
        }

    def test_status_enum_member_stores_its_value(self) -> None:
        patch = {"series": {"status": SeriesStatusEnum.HIATUS}}
        assert patch_series_attrs(patch) == {"status": "Hiatus"}

    def test_drops_empty_and_unknown_values(self) -> None:
        patch = {"series": {"end_year": None, "status": "Paused", "summary": ""}}
        assert patch_series_attrs(patch) == {}

    def test_no_series(self) -> None:
        assert patch_series_attrs({"issue": {"number": "1"}}) == {}
        assert patch_series_attrs(None) == {}


class OnlineTagSeriesAttrsTestCase(TestCase):
    """An online match's series attributes survive its write and re-read."""

    @override
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cache.clear()
        codex_init()

    @override
    def setUp(self) -> None:
        cache.clear()
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.path = _TMP_DIR / f"{_FILENAME_SERIES} 001.cbz"  # pyright: ignore[reportUninitializedInstanceVariable]
        _untagged_cbz(self.path)
        self.library = Library.objects.create(path=str(_TMP_DIR), events=False)  # pyright: ignore[reportUninitializedInstanceVariable]
        self._import(
            ImportTask(self.library.pk, files_created=frozenset({str(self.path)}))
        )
        self.comic = Comic.objects.select_related("series").get(path=str(self.path))  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    @staticmethod
    def _import(task: ImportTask) -> None:
        run_full_import(ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event()))

    def _online_tag(self) -> BulkTagWriteTask:
        """Run a pass over the comic and return the write it flushed."""
        queue = FakeQueue()
        runner = TagPassRunner(
            double(logger),
            double(queue),
            double(_NoopStatusController()),
            lambda _state: None,
            lambda _state: None,
        )
        state = double(
            SimpleNamespace(
                session=_MatchedSession(),
                cancelled=False,
                pending_paths=[],
                total_comics=0,
                completed_comics=0,
                path_to_pk={self.path: self.comic.pk},
                collected_tags={},
                effort="balanced",
                sources=("metron",),
                merge_all_sources=False,
                mode="update",
                formats=("COMIC_INFO",),
                delete_original=False,
                rename=False,
            )
        )
        runner.collect_results(state, [self.path], flush_writes=True)
        (write_task,) = _queued(queue, BulkTagWriteTask)
        return write_task

    def _write_and_reread(self, write_task: BulkTagWriteTask) -> ImportTask:
        """Write the tags and run the re-read the writer queued."""
        queue = FakeQueue()
        _make_writer(queue).write_tags(write_task)
        (import_task,) = _queued(queue, ImportTask)
        self._import(import_task)
        return import_task

    def test_series_attrs_land_on_the_matched_series(self) -> None:
        assert self.comic.series.name == _FILENAME_SERIES
        old_series_pk = self.comic.series.pk

        import_task = self._write_and_reread(self._online_tag())

        assert import_task.series_attrs == {
            str(self.path): patch_series_attrs(_MATCH_TAGS)
        }
        self.comic.refresh_from_db()
        series = self.comic.series
        assert series.pk != old_series_pk
        assert series.name == _SERIES
        assert series.publisher.name == "Marvel"
        # ComicInfo holds none of them, the start year included.
        assert series.start_year == _START_YEAR
        assert series.end_year == _END_YEAR
        assert series.status == _STATUS
        assert series.summary == _SUMMARY

    def test_a_file_only_reimport_keeps_them(self) -> None:
        self._write_and_reread(self._online_tag())

        # The watcher's re-read of the same file carries no attributes.
        self._import(
            ImportTask(
                self.library.pk,
                files_modified=frozenset({str(self.path)}),
                force_import_metadata=True,
                check_metadata_mtime=False,
            )
        )

        series = Series.objects.get(name=_SERIES)
        assert series.end_year == _END_YEAR
        assert series.status == _STATUS
        assert series.summary == _SUMMARY

"""
What an import's reading-list passes cost, and that they stay cheap (C1).

- The post-phase of an import costs a handful of queries when there are no
  lists and no arc tags.
- The live sync reads each list's items in one query for all, and the
  staleness check hands the rows and comics it read to the sync, which
  read them all a second time.
- A burst of imports queues a full rematch each; one that began after a
  queued one was queued covers it.
- A rematch or live sync that changed nothing tells no browser.
"""

from threading import Lock
from typing import Final, override
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from loguru import logger

from codex.librarian.notifier.tasks import READING_LISTS_CHANGED_TASK
from codex.librarian.scribe.importer.init import Counts
from codex.librarian.scribe.importer.readinglists import ReadingListsImporter
from codex.librarian.scribe.readinglists.live import add_item, reconcile_list, sync_live
from codex.librarian.scribe.readinglists.tasks import (
    ReadingListLiveSyncTask,
    ReadingListRematchTask,
)
from codex.librarian.scribe.readinglists.worker import ReadingListWorker
from codex.models import ReadingList, ReadingListEntry, ReadingListSource
from codex.models.readinglist import ReadingListMatchTier
from tests.onlinetag_session_fakes import double
from tests.test_reading_list_notify import _with_queue
from tests.test_reading_lists import ReadingListFixture

_EMPTY_POST_PHASE: Final = 7
_UNCHANGED_SYNC: Final = 6
_STALE_SYNC: Final = 30
_REMATCH: Final = "codex.librarian.scribe.readinglists.worker.rematch"


def _entries() -> list[tuple]:
    return list(
        ReadingListEntry.objects.order_by(
            "reading_list_id", "position", "pk"
        ).values_list("reading_list_id", "position", "comic_id", "live_source_id")
    )


class ImportPostPhaseTests(ReadingListFixture):
    """Three lists that each hold a series and a volume."""

    def _holders(self) -> None:
        comic = self.comics[0]
        for n in range(3):
            holder = ReadingList.objects.create(name=f"Holder {n}")
            add_item(holder, "series", comic.series_id)
            add_item(holder, "volumes", comic.volume_id)
            reconcile_list(holder)

    def test_no_lists_no_arcs_costs_almost_nothing(self) -> None:
        """An import that touched comics and tags pays a few queries."""
        importer, queue = _with_queue(
            ReadingListsImporter, counts=Counts(comic=1, tags=1, link=1)
        )
        with self.assertNumQueries(_EMPTY_POST_PHASE):
            importer.sync_reading_lists()
        assert READING_LISTS_CHANGED_TASK not in queue

    def test_an_unchanged_sync_reads_little(self) -> None:
        self._holders()
        with self.assertNumQueries(_UNCHANGED_SYNC):
            assert sync_live() == 0

    def test_a_stale_sync_reads_each_collection_once(self) -> None:
        """The same rows as a sync from scratch, for fewer queries."""
        self._holders()
        before = _entries()
        ReadingListSource.objects.filter(kind="collection").update(revision="")
        with CaptureQueriesContext(connection) as queries:
            sync_live()
        assert len(queries) == _STALE_SYNC
        assert _entries() == before


class _Queue:
    """What the worker puts on the librarian queue."""

    def __init__(self) -> None:
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


class RematchCostTests(ReadingListFixture):
    """The rematch a burst of imports queues, and what it tells browsers."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.queue = _Queue()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.worker = ReadingListWorker(logger, double(self.queue), Lock())  # pyright: ignore[reportUninitializedInstanceVariable]
        ReadingListWorker._full_rematch_began = 0.0  # noqa: SLF001

    @staticmethod
    def _gaps() -> ReadingList:
        """Make a list with one issue the library does not have."""
        gaps = ReadingList.objects.create(name="Gaps")
        ReadingListEntry.objects.create(
            reading_list=gaps,
            series_name="Absent",
            issue="1",
            match_tier=ReadingListMatchTier.NONE,
        )
        return gaps

    def test_a_burst_runs_one_full_rematch(self) -> None:
        """Two queued before the first began: the second is covered."""
        first, second = ReadingListRematchTask(), ReadingListRematchTask()
        self._gaps()
        with patch(_REMATCH, return_value=0) as rematch:
            self.worker.rematch_lists(first)
            self.worker.rematch_lists(second)
            later = ReadingListRematchTask()
            self.worker.rematch_lists(later)
        assert rematch.call_count == 2  # noqa: PLR2004

    def test_a_narrow_rematch_always_runs(self) -> None:
        task = ReadingListRematchTask(list_pks=(self._gaps().pk,))
        self.worker.rematch_lists(ReadingListRematchTask())
        with patch(_REMATCH, return_value=0) as rematch:
            self.worker.rematch_lists(task)
        assert rematch.call_count == 1

    def test_finding_nothing_tells_no_one(self) -> None:
        self._gaps()
        self.worker.rematch_lists(ReadingListRematchTask())
        assert READING_LISTS_CHANGED_TASK not in self.queue.items

    def test_a_live_sync_that_changed_nothing_tells_no_one(self) -> None:
        self.worker.sync_live_lists(ReadingListLiveSyncTask())
        assert READING_LISTS_CHANGED_TASK not in self.queue.items

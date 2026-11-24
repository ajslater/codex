"""
Merging a second scan into a running online-tag session.

A second ``BulkOnlineTagTask`` enqueued mid-scan is merged into the live
session. Comics the session already holds must be recognized, or a scan
whose selection overlaps (re-picking a folder to catch additions is the
natural gesture) queues them twice: inflated totals and duplicate lookups
against rate-limited sources.
"""

from pathlib import Path
from queue import SimpleQueue
from typing import Any, Final

from codex.librarian.onlinetag.session_state import SessionState
from codex.librarian.onlinetag.tasks import BulkOnlineTagTask
from codex.models import Comic
from tests.onlinetag_session_fakes import (
    FakeSession,
    OnlineTagSessionTestCase,
    double,
    make_comic,
)

#: The comic the session already holds, plus the one merged into it.
_HELD_PLUS_NEW: Final = 2


class MergeFixture(OnlineTagSessionTestCase):
    """A session state holding one comic, and a sibling to merge into it."""

    @staticmethod
    def _state_holding(comic) -> SessionState:
        """Build a session state that already carries ``comic``."""
        return SessionState(
            session=double(FakeSession()),
            path_to_pk={Path(comic.path): comic.pk},
            total_comics=1,
        )

    @staticmethod
    def _sibling_of(comic: Comic) -> Comic:
        """Create a second comic in the same library as ``comic``."""
        path = Path(comic.path).parent / "d.cbz"
        path.touch()
        return Comic.objects.create(
            library=comic.library,
            path=path,
            issue_number=2,
            name="d",
            publisher=comic.publisher,
            imprint=comic.imprint,
            series=comic.series,
            volume=comic.volume,
            size=1,
            file_type="CBZ",
        )


class MergeTaskTests(MergeFixture):
    """_merge_task adds only comics the session isn't already tagging."""

    def test_already_queued_comic_is_not_merged_again(self) -> None:
        """An overlapping selection must not re-queue a comic."""
        comic = make_comic()
        state = self._state_holding(comic)
        task = BulkOnlineTagTask(comic_pks=frozenset({comic.pk}), session_id="s")

        self.manager._merge_task(state, task)  # noqa: SLF001

        assert state.total_comics == 1
        assert state.pending_paths == []
        assert state.path_to_pk == {Path(comic.path): comic.pk}

    def test_new_comic_is_merged(self) -> None:
        """A comic the session doesn't hold is queued and counted."""
        held = make_comic()
        state = self._state_holding(held)
        new_comic = self._sibling_of(held)
        task = BulkOnlineTagTask(comic_pks=frozenset({new_comic.pk}), session_id="s")

        self.manager._merge_task(state, task)  # noqa: SLF001

        assert state.total_comics == _HELD_PLUS_NEW
        assert state.pending_paths == [Path(new_comic.path)]
        assert state.path_to_pk[Path(new_comic.path)] == new_comic.pk


# What the session the queued task arrives into was started with.
_RUNNING_PARAMS: Final = {
    "sources": ["metron"],
    "mode": "auto",
    "effort": "",
    "prompts_mode": "ask",
    "delete_original": False,
    "merge_all_sources": False,
    "rename": False,
    "ids": {},
}


class DrainMergeTests(MergeFixture):
    """
    A task arriving mid-scan joins the session only when it would run alike.

    A Tag by ID session fetches every comic by its pinned issue, so a comic
    merged into it would be written with another comic's tags. A task with
    other sources or options would run under the session's instead.
    """

    def _drain(self, running: dict[str, Any], **task_kwargs) -> tuple:
        held = make_comic()
        state = self._state_holding(held)
        state.resume_params = running
        new_comic = self._sibling_of(held)
        task = BulkOnlineTagTask(
            comic_pks=frozenset({new_comic.pk}), session_id="second", **task_kwargs
        )
        queue: SimpleQueue = SimpleQueue()
        queue.put(task)
        self.manager.thread_queue = queue
        self.manager._drain_thread_queue(state)  # noqa: SLF001
        left = []
        while not queue.empty():
            left.append(queue.get_nowait())
        return state, task, left

    def test_a_task_is_not_merged_into_a_pinned_session(self) -> None:
        """A second scan during Tag by ID stays queued as its own session."""
        running = {**_RUNNING_PARAMS, "ids": {"metron": 123}}
        state, task, left = self._drain(running, sources=("metron",))
        assert state.pending_paths == []
        assert state.total_comics == 1
        assert left == [task]

    def test_a_pinned_task_is_not_merged(self) -> None:
        """A Tag by ID arriving mid-scan keeps its pinned id: its own session."""
        state, task, left = self._drain(
            _RUNNING_PARAMS, sources=("metron",), ids={"metron": 123}
        )
        assert state.pending_paths == []
        assert left == [task]

    def test_a_task_with_other_options_is_not_merged(self) -> None:
        """Other sources or options run as their own session."""
        state, task, left = self._drain(
            _RUNNING_PARAMS, sources=("metron", "comicvine")
        )
        assert state.pending_paths == []
        assert left == [task]

    def test_a_matching_task_is_merged(self) -> None:
        """The same options and no pinned id: the comics join the session."""
        state, _, left = self._drain(_RUNNING_PARAMS, sources=("metron",))
        assert state.total_comics == _HELD_PLUS_NEW
        assert len(state.pending_paths) == 1
        assert left == []

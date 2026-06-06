"""Run online-tag passes against the comicbox session."""

from __future__ import annotations

from time import monotonic
from typing import TYPE_CHECKING, Any

from codex.librarian.onlinetag.status import OnlineLookupStatus
from codex.librarian.scribe.tasks import BulkTagWriteTask

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from multiprocessing import Queue
    from pathlib import Path

    from loguru._logger import Logger

    from codex.librarian.onlinetag.session_state import SessionState
    from codex.librarian.status_controller import StatusController


_RATE_LIMIT_THRESHOLD = 10


class TagPassRunner:
    """Drive tag_many() over a session and flush write tasks."""

    def __init__(
        self,
        log: Logger,
        librarian_queue: Queue,
        status_controller: StatusController,
        drain_queue: Callable[[SessionState | None], None],
    ) -> None:
        """Wire the runner with its log, queue, status controller, and drain callback."""
        self.log = log
        self.librarian_queue = librarian_queue
        self.status_controller = status_controller
        self._drain_queue = drain_queue
        self.rate_limited: bool = False
        self.lookup_status: OnlineLookupStatus | None = None

    def _flush_batch(self, state: SessionState, batch: dict[int, dict]) -> None:
        """Write a batch of collected tags."""
        if not batch:
            return
        write_task = BulkTagWriteTask(
            comic_pks=frozenset(batch.keys()),
            per_comic_patches=dict(batch),
            mode=state.mode,
            formats=state.formats,
            delete_original=state.delete_original,
        )
        self.librarian_queue.put(write_task)
        self.log.info(f"Online tag: flushed write batch of {len(batch)} comics.")
        batch.clear()

    def _detect_rate_limit_recovery(self, status: OnlineLookupStatus) -> bool:
        """Detect a rate-limit recovery and surface it in status."""
        elapsed = monotonic() - status.since_updated if status.since_updated else 0
        was_rate_limited = self.rate_limited or elapsed > _RATE_LIMIT_THRESHOLD
        if not self.rate_limited and was_rate_limited:
            status.subtitle = f"rate limited ~{elapsed:.0f}s"
            status.since_updated = 0
            self.status_controller.update(status, notify=True)
        return was_rate_limited

    def _advance_result_status(
        self, state: SessionState, status: OnlineLookupStatus
    ) -> None:
        """Increment counters and push status after a single result."""
        state.completed_comics += 1
        status.complete = state.completed_comics
        status.total = state.total_comics
        if not self.rate_limited:
            status.subtitle = ""
        self.rate_limited = False
        self.status_controller.update(status)

    @staticmethod
    def _store_result_tags(
        state: SessionState,
        result: Any,
        batch: dict[int, dict],
        *,
        flush_writes: bool,
    ) -> None:
        """Stash tags from one result into batch or collected_tags."""
        if not result.tags or result.error:
            return
        pk = state.path_to_pk.get(result.path)
        if pk is None:
            return
        if flush_writes:
            batch[pk] = result.tags
        else:
            state.collected_tags[pk] = result.tags

    def _run_pass(
        self,
        state: SessionState,
        paths: list[Path],
        status: OnlineLookupStatus,
        batch: dict[int, dict],
        *,
        flush_writes: bool,
    ) -> None:
        """Run one tag_many pass, updating status and draining the queue."""
        for result in state.session.tag_many(paths):
            if state.cancelled:
                break
            self._drain_queue(state)
            was_rate_limited = self._detect_rate_limit_recovery(status)
            self._advance_result_status(state, status)
            self._store_result_tags(state, result, batch, flush_writes=flush_writes)
            if flush_writes and was_rate_limited and batch:
                self._flush_batch(state, batch)

    def collect_results(
        self,
        state: SessionState,
        paths: Iterable[Path],
        *,
        flush_writes: bool = False,
    ) -> None:
        """Iterate tag_many, merging new tasks that arrive mid-run."""
        path_list = list(paths)
        state.total_comics += len(path_list)
        status = OnlineLookupStatus()
        status.total = state.total_comics
        status.complete = state.completed_comics
        self.lookup_status = status
        self.rate_limited = False
        self.status_controller.start(status)

        batch: dict[int, dict] = {}
        self._run_pass(state, path_list, status, batch, flush_writes=flush_writes)

        while state.pending_paths and not state.cancelled:
            new_paths = list(state.pending_paths)
            state.pending_paths.clear()
            status.total = state.total_comics
            self.status_controller.update(status, notify=True)
            self._run_pass(state, new_paths, status, batch, flush_writes=flush_writes)

        if flush_writes:
            self._flush_batch(state, batch)

        self.lookup_status = None
        self.status_controller.finish(status)

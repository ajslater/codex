"""Manage online tagging sessions and their lifecycle."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any

from comicbox.events import Event, PromptDeferred, RateLimited
from comicbox.online_session import (
    MatchMode,
    OnlineCredentials,
    OnlineSession,
    PromptResponse,
)

from codex.librarian.notifier.tasks import ONLINE_TAG_PROMPT_TASK
from codex.librarian.onlinetag.status import OnlineLookupStatus
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.librarian.status_controller import StatusController
from codex.models.admin import ComicboxTaggingDefaults
from codex.models.comic import Comic

if TYPE_CHECKING:
    from collections.abc import Iterable
    from multiprocessing import Queue

    from comicbox.online_session import DeferredPrompt, OnlinePrompt
    from loguru._logger import Logger

    from codex.librarian.onlinetag.tasks import BulkOnlineTagTask


@dataclass
class SessionState:
    """Tracks a single online tagging session."""

    session: OnlineSession
    collected_tags: dict[int, dict[str, Any]] = field(default_factory=dict)
    deferred_prompts: list[DeferredPrompt] = field(default_factory=list)
    resolved_count: int = 0
    total_prompts: int = 0
    event: threading.Event = field(default_factory=threading.Event)
    path_to_pk: dict[Path, int] = field(default_factory=dict)
    pending_paths: list[Path] = field(default_factory=list)
    mode: str = "additive"
    formats: tuple[str, ...] = ("COMIC_INFO",)
    delete_original: bool = False
    cancelled: bool = False
    total_comics: int = 0
    completed_comics: int = 0


class _CodexPromptHandler:
    """Fallback PromptHandler for non-deferred mode."""

    def request(self, _prompt: OnlinePrompt) -> PromptResponse:
        """Skip by default — primary flow uses defer mode."""
        return PromptResponse(action="skip", payload=None)


def _serialize_candidate(c) -> dict[str, Any]:
    """Serialize a comicbox Candidate to a JSON-safe dict."""
    summary = c.summary
    return {
        "source": c.source,
        "issue_id": c.issue_id,
        "summary": {
            "series": getattr(summary, "series", ""),
            "issue": getattr(summary, "issue", ""),
            "year": getattr(summary, "year", None),
            "publisher": getattr(summary, "publisher", ""),
            "cover_url": getattr(summary, "cover_url", ""),
        },
        "score": c.score,
        "url": getattr(c, "url", ""),
    }


class OnlineTagSessionManager:
    """Manage online tagging sessions."""

    def __init__(self, log: Logger, librarian_queue: Queue, thread_queue=None) -> None:
        """Initialize the session manager."""
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.Lock()
        self.log = log
        self.librarian_queue = librarian_queue
        self.thread_queue = thread_queue
        self.status_controller = StatusController(log, librarian_queue)
        self._active_session_id: str | None = None
        self._lookup_status: OnlineLookupStatus | None = None
        self._rate_limited: bool = False

    def _build_credentials(self) -> OnlineCredentials | None:
        """Load and decrypt credentials from the defaults model."""
        try:
            defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        except ComicboxTaggingDefaults.DoesNotExist:
            return None
        if not defaults.metron_user and not defaults.comicvine_key:
            return None
        return OnlineCredentials(
            metron_user=defaults.metron_user or "",
            metron_password=defaults.metron_password or "",
            metron_url=defaults.metron_url or "",
            comicvine_key=defaults.comicvine_key or "",
            comicvine_url=defaults.comicvine_url or "",
        )

    def _persist_session(self, session_id: str) -> None:
        """Write the active session ID to the database."""
        ComicboxTaggingDefaults.objects.filter(pk=1).update(
            active_session_id=session_id
        )

    def _persist_prompts(self, session_id: str) -> None:
        """Serialize and persist current deferred prompts to the database."""
        prompts = self.get_pending_prompts(session_id)
        ComicboxTaggingDefaults.objects.filter(pk=1).update(active_prompts=prompts)

    def _clear_session_db(self) -> None:
        """Clear active session state from the database."""
        ComicboxTaggingDefaults.objects.filter(pk=1).update(
            active_session_id="", active_prompts=[]
        )

    _RATE_LIMIT_THRESHOLD = 10

    def _on_event(self, event: Event) -> None:
        """Handle comicbox online events."""
        match event:
            case RateLimited():
                self._rate_limited = True
                if self._lookup_status:
                    secs = event.retry_after_seconds
                    wait = f" {secs:.0f}s" if secs else ""
                    self._lookup_status.subtitle = (
                        f"rate limited by {event.source}{wait}"
                    )
                    self._lookup_status.since_updated = 0
                    self.status_controller.update(self._lookup_status, notify=True)
            case PromptDeferred():
                if self._active_session_id:
                    self._sync_deferred_prompts(self._active_session_id)

    def _sync_deferred_prompts(self, session_id: str) -> None:
        """Snapshot deferred prompts from the session and persist + notify."""
        with self._lock:
            state = self._sessions.get(session_id)
        if not state:
            return
        state.deferred_prompts = list(state.session.deferred_prompts())
        state.total_prompts = len(state.deferred_prompts)
        self._persist_prompts(session_id)
        self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)

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

    def _run_tag_many(
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
            self._drain_thread_queue(state)
            elapsed = monotonic() - status.since_updated if status.since_updated else 0
            was_rate_limited = (
                self._rate_limited or elapsed > self._RATE_LIMIT_THRESHOLD
            )
            if not self._rate_limited and was_rate_limited:
                status.subtitle = f"rate limited ~{elapsed:.0f}s"
                status.since_updated = 0
                self.status_controller.update(status, notify=True)
            state.completed_comics += 1
            status.complete = state.completed_comics
            status.total = state.total_comics
            if not self._rate_limited:
                status.subtitle = ""
            self._rate_limited = False
            self.status_controller.update(status)
            if result.tags and not result.error:
                pk = state.path_to_pk.get(result.path)
                if pk is not None:
                    if flush_writes:
                        batch[pk] = result.tags
                    else:
                        state.collected_tags[pk] = result.tags
            if flush_writes and was_rate_limited and batch:
                self._flush_batch(state, batch)

    def _collect_results(
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
        self._lookup_status = status
        self._rate_limited = False
        self.status_controller.start(status)

        batch: dict[int, dict] = {}
        self._run_tag_many(state, path_list, status, batch, flush_writes=flush_writes)

        while state.pending_paths and not state.cancelled:
            new_paths = list(state.pending_paths)
            state.pending_paths.clear()
            status.total = state.total_comics
            self.status_controller.update(status, notify=True)
            self._run_tag_many(
                state, new_paths, status, batch, flush_writes=flush_writes
            )

        if flush_writes:
            self._flush_batch(state, batch)

        self._lookup_status = None
        self.status_controller.finish(status)

    def _drain_thread_queue(self, state: SessionState | None = None) -> None:
        """Process pending tasks from the thread queue."""
        if not self.thread_queue:
            return
        from codex.librarian.onlinetag.tasks import (
            BulkOnlineTagTask,
            OnlineTagAbortTask,
            OnlineTagPromptResponseTask,
        )

        while True:
            try:
                item = self.thread_queue.get_nowait()
            except Exception:
                break
            match item:
                case BulkOnlineTagTask() if state is not None:
                    self._merge_task(state, item)
                case OnlineTagPromptResponseTask():
                    self.resolve_prompt(
                        item.session_id,
                        item.prompt_fingerprint,
                        item.action,
                        item.payload,
                        item.chosen_volume_id,
                    )
                case OnlineTagAbortTask():
                    self.cancel_session(item.session_id)
                case _:
                    self.thread_queue.put(item)
                    break

    def _merge_task(self, state: SessionState, task: Any) -> None:
        """Merge a new BulkOnlineTagTask's comics into the running session."""
        comics = Comic.objects.filter(pk__in=task.comic_pks).only("pk", "path")
        new_paths = {}
        for comic in comics:
            path = Path(comic.path)
            if path not in state.path_to_pk.values():
                new_paths[path] = comic.pk
        if not new_paths:
            return
        for path, pk in new_paths.items():
            state.path_to_pk[path] = pk
            state.pending_paths.append(path)
        state.total_comics += len(new_paths)
        self.log.info(
            f"Online tag: merged {len(new_paths)} comics, "
            f"total now {state.total_comics}"
        )

    def _wait_for_prompts(
        self, state: SessionState, session_id: str, timeout: int
    ) -> bool:
        """Notify admins and block until prompts are resolved or timeout."""
        deferred = state.session.deferred_prompts()
        if not deferred:
            return True

        state.deferred_prompts = list(deferred)
        state.total_prompts = len(deferred)
        state.resolved_count = 0

        self._persist_prompts(session_id)
        self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)

        elapsed = 0
        poll_interval = 1
        while elapsed < timeout and not state.event.is_set() and not state.cancelled:
            self._drain_thread_queue(state)
            if state.event.wait(timeout=poll_interval):
                break
            elapsed += poll_interval

        if not state.event.is_set() and not state.cancelled:
            self.log.warning(
                f"Online tag session {session_id}: prompt timeout after {timeout}s."
            )

        return not state.cancelled

    def _run_deferred_pass(self, state: SessionState) -> None:
        """Pass 2: re-run deferred files with preloaded cache."""
        state.session.set_defer_prompts(defer=False)
        deferred_paths = [d.path for d in state.deferred_prompts if d.path]
        self._collect_results(state, deferred_paths)

    def _enqueue_write(self, state: SessionState, session_id: str) -> None:
        """Enqueue a BulkTagWriteTask for all collected tags."""
        if not state.collected_tags:
            return
        write_task = BulkTagWriteTask(
            comic_pks=frozenset(state.collected_tags.keys()),
            per_comic_patches=state.collected_tags,
            mode=state.mode,
            formats=state.formats,
            delete_original=state.delete_original,
        )
        self.librarian_queue.put(write_task)
        self.log.info(
            f"Online tag session {session_id}: queued write for {len(state.collected_tags)} comics."
        )

    def run_session(self, task: BulkOnlineTagTask) -> None:
        """Execute a full online tagging session."""
        comics = Comic.objects.filter(pk__in=task.comic_pks).only("pk", "path")
        comic_paths = {comic.pk: Path(comic.path) for comic in comics}
        if not comic_paths:
            self.log.debug("Online tag: no comics found.")
            return

        credentials = self._build_credentials()
        if not credentials:
            self.log.warning("Online tag: no credentials configured.")
            return

        defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        session = OnlineSession(
            sources=task.sources,
            credentials=credentials,
            mode=MatchMode(task.mode),
            defer_prompts=True,
            on_event=self._on_event,
            prompt_handler=_CodexPromptHandler(),  # pyright: ignore[reportArgumentType]
        )
        state = SessionState(
            session=session,
            path_to_pk={path: pk for pk, path in comic_paths.items()},
            mode="update",
            formats=tuple(defaults.default_formats),
            delete_original=task.delete_original,
            total_comics=0,
            completed_comics=0,
        )
        self._active_session_id = task.session_id
        with self._lock:
            self._sessions[task.session_id] = state
        self._persist_session(task.session_id)

        try:
            self._collect_results(state, comic_paths.values(), flush_writes=True)
            if state.cancelled:
                return
            if self._wait_for_prompts(
                state, task.session_id, defaults.prompt_timeout_seconds
            ):
                self._run_deferred_pass(state)
            if not state.cancelled and state.collected_tags:
                self._enqueue_write(state, task.session_id)
        finally:
            self._cleanup(task.session_id)

    def resolve_prompt(
        self,
        session_id: str,
        fingerprint: str,
        action: str,
        payload: Any,
        chosen_volume_id: int | None,
    ) -> None:
        """Resolve a deferred prompt and check if all are done."""
        with self._lock:
            state = self._sessions.get(session_id)
        if not state:
            self.log.warning(f"resolve_prompt: unknown session {session_id}")
            return
        state.session.preload_resolution(
            fingerprint,
            action=action,  # pyright: ignore[reportArgumentType]
            payload=payload,
            chosen_volume_id=chosen_volume_id,
        )
        state.resolved_count += 1

        state.deferred_prompts = [
            dp for dp in state.deferred_prompts if dp.fingerprint != fingerprint
        ]
        self._persist_prompts(session_id)
        self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)

        if state.resolved_count >= state.total_prompts:
            state.event.set()

    def get_pending_prompts(self, session_id: str) -> list[dict[str, Any]]:
        """Serialize deferred prompts for the REST endpoint."""
        with self._lock:
            state = self._sessions.get(session_id)
        if not state or not state.deferred_prompts:
            return []
        return [
            {
                "fingerprint": dp.fingerprint,
                "path": str(dp.path) if dp.path else "",
                "source": dp.source,
                "candidates": [_serialize_candidate(c) for c in dp.candidates],
                "mode": dp.mode,
            }
            for dp in state.deferred_prompts
        ]

    def cancel_session(self, session_id: str) -> None:
        """Cancel a running session."""
        with self._lock:
            state = self._sessions.get(session_id)
        if not state:
            return
        state.cancelled = True
        state.session.cancel()
        state.event.set()
        self.log.info(f"Online tag session {session_id} cancelled.")

    def _cleanup(self, session_id: str) -> None:
        """Remove session state."""
        with self._lock:
            self._sessions.pop(session_id, None)
        self._active_session_id = None
        self._clear_session_db()

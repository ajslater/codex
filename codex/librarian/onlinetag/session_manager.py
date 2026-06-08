"""
Manage online tagging sessions and their lifecycle.

A tagging *scan* (``run_session``) is non-blocking: it auto-matches and
writes the confident comics in one pass, persists any ambiguous matches as
deferred *prompts* in the cache, then finishes and releases the thread. The
prompts linger until an admin answers them. Answering a prompt
(``resolve_prompt``) is fully decoupled from the original scan: it builds a
*fresh* session and applies that single comic's chosen match, because the
deferred-prompt fingerprint is deterministic across processes.
"""

from __future__ import annotations

import threading
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any, cast

from comicbox.events import Event, PromptDeferred, RateLimited
from comicbox.online_session import MatchMode, OnlineCredentials, OnlineSession
from humanize import naturaldelta

from codex.librarian.notifier.tasks import (
    ONLINE_TAG_PROMPT_TASK,
    TAG_WRITE_ERRORS_CHANGED_TASK,
)
from codex.librarian.onlinetag.explicit_id import fetch_tags_by_explicit_id
from codex.librarian.onlinetag.session_cache import (
    add_pending_prompts,
    get_pending_prompts,
    remove_pending_prompt,
    set_active_scan_id,
    set_pending_prompts,
)
from codex.librarian.onlinetag.session_state import (
    CodexPromptHandler,
    SessionState,
    serialize_candidate,
)
from codex.librarian.onlinetag.tag_pass_runner import TagPassRunner
from codex.librarian.onlinetag.tasks import (
    BulkOnlineTagTask,
    OnlineTagAbortTask,
    OnlineTagByIdTask,
)
from codex.librarian.scribe.tagwrite_errors import add_tag_write_error
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.librarian.status_controller import StatusController
from codex.models.admin import ComicboxTaggingDefaults
from codex.models.comic import Comic

if TYPE_CHECKING:
    from multiprocessing import Queue
    from typing import Literal

    from loguru._logger import Logger


class OnlineTagSessionManager:
    """Manage online tagging sessions."""

    def __init__(self, log: Logger, librarian_queue: Queue, thread_queue=None) -> None:
        """Initialize the session manager."""
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.RLock()
        self.log = log
        self.librarian_queue = librarian_queue
        self.thread_queue = thread_queue
        self.status_controller = StatusController(log, librarian_queue)
        self._active_session_id: str | None = None
        self._pass_runner = TagPassRunner(
            log, librarian_queue, self.status_controller, self._drain_thread_queue
        )

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

    @staticmethod
    def _source_has_credentials(credentials: OnlineCredentials, source: str) -> bool:
        """Whether ``credentials`` actually carries auth for ``source``."""
        if source == "metron":
            return bool(credentials.metron_user and credentials.metron_password)
        if source == "comicvine":
            return bool(credentials.comicvine_key)
        return False

    # --- tag by explicit id (no search) --------------------------------

    def tag_by_id(self, task: OnlineTagByIdTask) -> None:
        """
        Tag one comic by a known online issue id, skipping search entirely.

        The operator already knows the exact Metron / Comic Vine issue, so we
        fetch that record directly and hand the tags to the same
        ``BulkTagWriteTask`` write + re-import path the scan uses. A wrong or
        unknown id resolves to nothing; that surfaces in the admin Tagging-tab
        error panel rather than silently re-writing the comic's existing tags.
        """
        comic = Comic.objects.filter(pk=task.comic_pk).only("pk", "path").first()
        if not comic:
            self.log.warning(f"Online tag by id: comic {task.comic_pk} not found.")
            return
        path = Path(comic.path)
        credentials = self._build_credentials()
        if not credentials or not self._source_has_credentials(
            credentials, task.source
        ):
            self.log.warning(
                f"Online tag by id: no {task.source} credentials configured."
            )
            return

        tags = fetch_tags_by_explicit_id(path, task.source, task.issue_id, credentials)
        if not tags:
            msg = f"No {task.source} issue found for id {task.issue_id}."
            self.log.warning(f"Online tag by id: {msg} ({path})")
            add_tag_write_error(str(path), msg)
            self.librarian_queue.put(TAG_WRITE_ERRORS_CHANGED_TASK)
            return

        write_task = BulkTagWriteTask(
            comic_pks=frozenset({comic.pk}),
            per_comic_patches={comic.pk: tags},
            mode="update",
            formats=task.formats,
            delete_original=task.delete_original,
        )
        self.librarian_queue.put(write_task)
        self.log.info(
            f"Online tag by id: applied {task.source}:{task.issue_id} to {path}."
        )

    # --- events --------------------------------------------------------

    def _active_state(self) -> SessionState | None:
        """Return the running scan's state, or None when no scan is in flight."""
        with self._lock:
            if not self._active_session_id:
                return None
            return self._sessions.get(self._active_session_id)

    def _on_event(self, event: Event) -> None:
        """Handle comicbox online events."""
        state = self._active_state()
        if state is not None:
            state.stats.record(event)
        match event:
            case RateLimited():
                self._pass_runner.rate_limited = True
                lookup_status = self._pass_runner.lookup_status
                if lookup_status:
                    secs = event.retry_after_seconds
                    wait = f" {secs:.0f}s" if secs else ""
                    lookup_status.subtitle = f"rate limited by {event.source}{wait}"
                    lookup_status.since_updated = 0
                    self.status_controller.update(lookup_status, notify=True)
            case PromptDeferred() if state is not None:
                self._persist_prompts(state)
            case _:
                pass

    # --- mid-scan queue draining ---------------------------------------

    def _drain_thread_queue(self, state: SessionState | None = None) -> None:
        """
        Process merge/abort tasks that arrive mid-scan.

        Prompt responses and skips are left on the queue for the normal
        thread loop to handle once the scan returns — they no longer need
        the live session, so there's no reason to service them inline.
        """
        if not self.thread_queue:
            return
        while True:
            try:
                item = self.thread_queue.get_nowait()
            except Exception:
                break
            match item:
                case BulkOnlineTagTask() if state is not None:
                    self._merge_task(state, item)
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
            f"Online tag: merged {len(new_paths)} comics, total now {state.total_comics}"
        )

    # --- prompt persistence --------------------------------------------

    @staticmethod
    def _serialize_prompt(state: SessionState, dp: Any, pk: int) -> dict[str, Any]:
        """Serialize a deferred prompt with everything needed to apply it later."""
        return {
            "fingerprint": dp.fingerprint,
            "pk": pk,
            "path": str(dp.path) if dp.path else "",
            "source": dp.source,
            "candidates": [serialize_candidate(c) for c in dp.candidates],
            "mode": getattr(dp.mode, "value", str(dp.mode)),
            "formats": list(state.formats),
            "delete_original": state.delete_original,
        }

    def _persist_prompts(self, state: SessionState) -> None:
        """Merge the scan's current deferred prompts into the cache and notify."""
        new: dict[str, Any] = {}
        for dp in state.session.deferred_prompts():
            if dp.path is None:
                continue
            pk = state.path_to_pk.get(dp.path)
            if pk is None:
                continue
            new[dp.fingerprint] = self._serialize_prompt(state, dp, pk)
        if new:
            add_pending_prompts(new)
            self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)

    # --- scan lifecycle ------------------------------------------------

    def run_session(self, task: BulkOnlineTagTask) -> None:
        """Execute a non-blocking online tagging scan (Pass 1 only)."""
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
        # "never" prompts: don't defer ambiguous matches. The CodexPromptHandler
        # returns a "skip" response by default, so with defer_prompts off comicbox
        # skips ambiguous comics inline instead of queueing them as deferred
        # prompts — only confidently-matched comics get written this run.
        defer_prompts = (
            task.prompts_mode != ComicboxTaggingDefaults.PromptsModeChoices.NEVER.value
        )
        session = OnlineSession(
            sources=task.sources,
            credentials=credentials,
            mode=MatchMode(task.mode),
            defer_prompts=defer_prompts,
            on_event=self._on_event,
            prompt_handler=CodexPromptHandler(),
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
        set_active_scan_id(task.session_id)

        start = monotonic()
        try:
            # Pass 1: auto-match and write the confident comics. When deferring,
            # ambiguous matches become deferred prompts persisted for later,
            # independent resolution; with "never" prompts they're skipped inline
            # and nothing is persisted. The scan never blocks waiting for answers.
            self._pass_runner.collect_results(
                state, comic_paths.values(), flush_writes=True
            )
            if defer_prompts:
                self._persist_prompts(state)
            self._log_summary(state, start)
        finally:
            with self._lock:
                self._sessions.pop(task.session_id, None)
            self._active_session_id = None
            set_active_scan_id("")

    def _log_summary(self, state: SessionState, start: float) -> None:
        """Log how the scan's comics resolved across sources, skips, and prompts."""
        stats = state.stats
        if not stats.total:
            self.log.debug("Online tag: session finished with no comics processed.")
            return
        level = "SUCCESS" if stats.matched else "INFO"
        self.log.log(level, stats.summary(elapsed=naturaldelta(monotonic() - start)))

    def cancel_session(self, session_id: str) -> None:
        """Cancel the in-flight scan (does not touch lingering prompts)."""
        with self._lock:
            state = self._sessions.get(session_id)
            if not state:
                return
            state.cancelled = True
            state.session.cancel()
        self.log.info(f"Online tag scan {session_id} cancelled.")

    def has_session(self, session_id: str) -> bool:
        """Whether ``session_id`` is currently running in-memory."""
        with self._lock:
            return session_id in self._sessions

    # --- prompt resolution (decoupled from any running scan) -----------

    def resolve_prompt(
        self,
        fingerprint: str,
        action: str,
        payload: Any,
        chosen_volume_id: int | None,
    ) -> None:
        """Apply (or skip) one deferred prompt via a fresh, standalone session."""
        prompt = get_pending_prompts().get(fingerprint)
        if not prompt:
            self.log.warning(f"resolve_prompt: unknown prompt {fingerprint!r}")
            return
        remove_pending_prompt(fingerprint)
        self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)
        if action == "skip":
            self.log.info(f"Online tag: skipped prompt for {prompt.get('path')!r}.")
            return
        self._apply_resolution(prompt, action, payload, chosen_volume_id)

    def skip_all_prompts(self) -> int:
        """Drop every pending prompt. Returns the number skipped."""
        prompts = get_pending_prompts()
        count = len(prompts)
        if count:
            set_pending_prompts({})
            self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)
        self.log.info(f"Online tag: skipped {count} prompt(s).")
        return count

    @staticmethod
    def _explicit_resolution(
        prompt: dict[str, Any], action: str, payload: Any
    ) -> tuple[str, Any]:
        """
        Pin a chosen candidate to its issue id.

        A fresh search may return candidates in a different order, so a bare
        ``choose`` index could select the wrong issue. Re-map the index to the
        candidate's stable ``issue_id`` and apply it as a ``manual`` pick,
        which fetches that exact issue regardless of search ordering.
        """
        if action != "choose":
            return action, payload
        candidates = prompt.get("candidates") or []
        index = payload if isinstance(payload, int) else None
        if index is None or not (0 <= index < len(candidates)):
            return action, payload
        chosen = candidates[index]
        issue_id = chosen.get("issue_id")
        source = chosen.get("source") or prompt.get("source")
        if issue_id and source:
            return "manual", f"{source}:{issue_id}"
        return action, payload

    def _apply_resolution(
        self,
        prompt: dict[str, Any],
        action: str,
        payload: Any,
        chosen_volume_id: int | None,
    ) -> None:
        """Build a fresh session, apply the chosen match, and enqueue a write."""
        pk = prompt.get("pk")
        path_str = prompt.get("path") or ""
        source = prompt.get("source") or ""
        if pk is None or not path_str or not source:
            self.log.warning("Online tag: prompt missing comic reference; skipping.")
            return
        credentials = self._build_credentials()
        if not credentials:
            self.log.warning("Online tag: no credentials for prompt resolution.")
            return

        action, payload = self._explicit_resolution(prompt, action, payload)
        session = OnlineSession(
            sources=(source,),
            credentials=credentials,
            mode=MatchMode(prompt.get("mode") or "auto"),
        )
        session.preload_resolution(
            prompt["fingerprint"],
            action=cast("Literal['choose', 'skip', 'manual']", action),
            payload=payload,
            chosen_volume_id=chosen_volume_id,
        )
        tags = self._first_tags(session, Path(path_str))
        if not tags:
            self.log.warning(f"Online tag: no tags resolved for {path_str}.")
            return
        write_task = BulkTagWriteTask(
            comic_pks=frozenset({pk}),
            per_comic_patches={pk: tags},
            mode="update",
            formats=tuple(prompt.get("formats") or ("COMIC_INFO",)),
            delete_original=bool(prompt.get("delete_original")),
        )
        self.librarian_queue.put(write_task)
        self.log.info(f"Online tag: applied resolved match for {path_str}.")

    @staticmethod
    def _first_tags(session: OnlineSession, path: Path) -> dict[str, Any] | None:
        """Return the tags from the single re-tagged comic, or None."""
        for result in session.tag_many([path]):
            if result.tags and not result.error:
                return result.tags
            break
        return None

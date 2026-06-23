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
from comicbox.exceptions import ComicboxError
from comicbox.online_session import MatchMode, OnlineCredentials, OnlineSession
from django.utils.timezone import now, timedelta
from humanize import naturaldelta

from codex.librarian.notifier.tasks import (
    ONLINE_TAG_PROMPT_TASK,
    TAG_WRITE_ERRORS_CHANGED_TASK,
)
from codex.librarian.onlinetag.estimate import estimate_seconds
from codex.librarian.onlinetag.explicit_id import fetch_tags_by_explicit_id
from codex.librarian.onlinetag.session_cache import (
    add_pending_prompts,
    get_pending_prompts,
    remove_pending_prompt,
    set_active_scan_id,
    set_pending_prompts,
)
from codex.librarian.onlinetag.session_snapshot import (
    USER_MATCHED,
    USER_SKIPPED,
    build_snapshot,
    clear_resolved_outcomes,
    clear_resume_state,
    clear_snapshot,
    record_resolution,
    remaining_pks,
    set_resume_state,
    set_snapshot,
)
from codex.librarian.onlinetag.session_state import (
    CodexPromptHandler,
    SessionState,
    serialize_candidate,
)
from codex.librarian.onlinetag.stored_id_prepass import build_stored_id_map
from codex.librarian.onlinetag.tag_pass_runner import TagPassRunner
from codex.librarian.onlinetag.tasks import (
    BulkOnlineTagTask,
    OnlineTagAbortTask,
    OnlineTagByIdTask,
    OnlineTagPromptResponseTask,
    OnlineTagSkipAllPromptsTask,
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
        # Throttle snapshot publishing to roughly the status-update cadence so
        # a fast (Metron) burst doesn't rewrite the cache per comic; forced
        # publishes (start, rate-limit, finish) bypass it.
        self._last_publish: float = 0.0
        self._pass_runner = TagPassRunner(
            log,
            librarian_queue,
            self.status_controller,
            self._drain_thread_queue,
            self._publish_snapshot,
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
        comic = (
            Comic.objects.filter(pk=task.comic_pk)
            .exclude(library__read_only=True)
            .only("pk", "path")
            .first()
        )
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

        try:
            tags = fetch_tags_by_explicit_id(
                path,
                task.source,
                task.issue_id,
                credentials,
                extra_ids=task.extra_ids,
            )
        except ComicboxError as exc:
            msg = f"Fetching {task.source} issue {task.issue_id} failed: {exc}"
            self.log.warning(f"Online tag by id: {msg} ({path})")
            add_tag_write_error(str(path), msg)
            self.librarian_queue.put(TAG_WRITE_ERRORS_CHANGED_TASK)
            return
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

    # --- live snapshot -------------------------------------------------

    _PUBLISH_DELTA = 4.0

    def _publish_snapshot(
        self,
        state: SessionState,
        *,
        active: bool = True,
        force: bool = False,
        session_id: str | None = None,
    ) -> None:
        """Fold scan state into the cache snapshot the admin status table reads."""
        try:
            elapsed = monotonic() - self._last_publish
            if not force and elapsed < self._PUBLISH_DELTA:
                return
            self._last_publish = monotonic()
            status = self._pass_runner.lookup_status
            eta = status.eta if status else None
            snapshot = build_snapshot(
                state,
                session_id=session_id or self._active_session_id or "",
                active=active,
                eta_epoch=eta.timestamp() if eta else None,
                source_retry_at=dict(self._pass_runner.source_retry_at),
                now_epoch=now().timestamp(),
            )
            set_snapshot(snapshot)
            # Persist the uncapped remainder + original params so a kill or
            # pause can resume what this scan never reached. A normal finish
            # leaves nothing remaining, which clears the key (not resumable).
            review_pks = {p.get("pk") for p in get_pending_prompts().values()}
            set_resume_state(state.resume_params, remaining_pks(state, review_pks))
        except Exception:
            self.log.exception("Publishing online tag session snapshot")

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
                    self._mark_rate_limited(lookup_status, state, event)
            case PromptDeferred() if state is not None:
                self._persist_prompts(state)
            case _:
                pass

    def _mark_rate_limited(
        self, status: Any, state: SessionState | None, event: RateLimited
    ) -> None:
        """Surface a rate-limit wait: live retry countdown + pushed-out eta."""
        secs = event.retry_after_seconds or 0
        status.subtitle = f"rate limited by {event.source}"
        # retry_at drives the live "retrying in M:SS" countdown in the admin
        # status item (the frontend ticks down to it). It fires once per retry
        # attempt, so each new attempt re-anchors the countdown.
        if secs:
            retry_at = now() + timedelta(seconds=secs)
            status.retry_at = retry_at
            # Per-source mirror for the snapshot's sources strip: the global
            # status carries one countdown, but the table shows which source is
            # waiting and for how long.
            if event.source:
                self._pass_runner.source_retry_at[event.source] = retry_at.timestamp()
        else:
            status.retry_at = None
        # Push the completion estimate out by the wait plus the work still
        # left, so the total countdown doesn't sail past zero while stalled.
        remaining = (
            max(0, state.total_comics - state.completed_comics)
            if state is not None
            else 0
        )
        work = (
            estimate_seconds(remaining, state.match_mode, state.sources)
            if state is not None
            else 0.0
        )
        total = secs + work
        status.eta = now() + timedelta(seconds=total) if total else None
        status.since_updated = 0
        self.status_controller.update(status, notify=True)
        if state is not None:
            self._publish_snapshot(state, force=True)

    # --- mid-scan queue draining ---------------------------------------

    def _drain_thread_queue(self, state: SessionState | None = None) -> None:
        """
        Process merge/abort/prompt tasks that arrive mid-scan.

        Prompt answers are serviced inline so the persistent cache reflects
        them promptly: a long scan (a rate-limited one can crawl for many
        minutes) used to leave answered prompts in the cache until it
        returned, so a browser refresh resurrected the just-answered prompt.
        Only the cache removal happens inline here (cheap, and race-free
        since it stays on this thread); the network re-fetch + write is
        deferred to ``_apply_deferred_resolutions`` after the scan releases
        the thread.
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
                case OnlineTagPromptResponseTask() if state is not None:
                    self._defer_prompt_response(state, item)
                case OnlineTagSkipAllPromptsTask() if state is not None:
                    self._defer_skip_all(state)
                case _:
                    self.thread_queue.put(item)
                    break

    # --- mid-scan prompt answers ---------------------------------------

    def _defer_prompt_response(
        self, state: SessionState, item: OnlineTagPromptResponseTask
    ) -> None:
        """Drop one answered prompt from the cache now; defer the apply."""
        fingerprint = item.prompt_fingerprint
        prompt = get_pending_prompts().get(fingerprint)
        if not prompt:
            return
        remove_pending_prompt(fingerprint)
        state.answered_fingerprints.add(fingerprint)
        self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)
        pk = prompt.get("pk")
        if item.action == "skip":
            record_resolution(pk, USER_SKIPPED)
            self.log.info(
                f"Online tag: skipped prompt for {prompt.get('path')!r} mid-scan."
            )
            return
        record_resolution(pk, USER_MATCHED)
        state.deferred_applies.append(
            (prompt, item.action, item.payload, item.chosen_volume_id)
        )

    def _defer_skip_all(self, state: SessionState) -> None:
        """Clear every pending prompt now; mark them answered for this scan."""
        prompts = get_pending_prompts()
        if not prompts:
            return
        state.answered_fingerprints.update(prompts.keys())
        for prompt in prompts.values():
            record_resolution(prompt.get("pk"), USER_SKIPPED)
        set_pending_prompts({})
        self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)
        self.log.info(f"Online tag: skipped {len(prompts)} prompt(s) mid-scan.")

    def _apply_deferred_resolutions(self, state: SessionState) -> None:
        """Apply mid-scan "choose"/"manual" answers once the scan is done."""
        if not state.deferred_applies:
            return
        applies = list(state.deferred_applies)
        state.deferred_applies.clear()
        for prompt, action, payload, chosen_volume_id in applies:
            try:
                self._apply_resolution(prompt, action, payload, chosen_volume_id)
            except Exception:
                path = prompt.get("path")
                self.log.exception(
                    f"Online tag: applying deferred prompt resolution for {path!r}"
                )

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
    def _serialize_prompt(
        dp: Any, pk: int, formats: tuple[str, ...], *, delete_original: bool
    ) -> dict[str, Any]:
        """Serialize a deferred prompt with everything needed to apply it later."""
        return {
            "fingerprint": dp.fingerprint,
            "pk": pk,
            "path": str(dp.path) if dp.path else "",
            "source": dp.source,
            "candidates": [serialize_candidate(c) for c in dp.candidates],
            "mode": getattr(dp.mode, "value", str(dp.mode)),
            "formats": list(formats),
            "delete_original": delete_original,
        }

    def _persist_prompts(self, state: SessionState) -> None:
        """Merge the scan's current deferred prompts into the cache and notify."""
        new: dict[str, Any] = {}
        for dp in state.session.deferred_prompts():
            if dp.path is None:
                continue
            # Don't resurrect a prompt the admin already answered mid-scan.
            if dp.fingerprint in state.answered_fingerprints:
                continue
            pk = state.path_to_pk.get(dp.path)
            if pk is None:
                continue
            new[dp.fingerprint] = self._serialize_prompt(
                dp, pk, state.formats, delete_original=state.delete_original
            )
        if new:
            add_pending_prompts(new)
            self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)

    # --- scan lifecycle ------------------------------------------------

    def _fetch_stored_id(
        self,
        path: Path,
        source_ids: dict[str, int],
        credentials: OnlineCredentials,
        *,
        merge_all_sources: bool,
    ) -> tuple[str, dict] | None:
        """
        Fetch one already-identified comic by its primary stored id.

        Returns ``(primary_source, tags)`` on success, or ``None`` when the id
        didn't resolve or the fetch errored — the caller leaves such a comic to
        the search pass. Under ``merge_all_sources`` the comic's other stored
        ids are fetched and merged onto the primary record.
        """
        primary_source, primary_id = next(iter(source_ids.items()))
        extra_ids = (
            tuple(
                (source, issue_id)
                for source, issue_id in source_ids.items()
                if source != primary_source
            )
            if merge_all_sources
            else ()
        )
        try:
            tags = fetch_tags_by_explicit_id(
                path, primary_source, primary_id, credentials, extra_ids=extra_ids
            )
        except ComicboxError as exc:
            self.log.warning(f"Online tag stored-id prefetch failed for {path}: {exc}")
            return None
        return (primary_source, tags) if tags else None

    def _commit_prefetch(
        self,
        state: SessionState,
        comic_paths: dict[int, Path],
        batch: dict[int, dict],
    ) -> None:
        """Count prefetched comics complete, drop them, and enqueue their write."""
        # Counted as already-complete so the status row's total and progress
        # cover them alongside the searched remainder. They stay in
        # ``path_to_pk`` (so the status table shows them as matched and Resume
        # skips them via ``written_paths``) but leave ``comic_paths`` so the
        # search pass never looks them up.
        state.total_comics += len(batch)
        state.completed_comics += len(batch)
        for pk in batch:
            comic_paths.pop(pk, None)
        write_task = BulkTagWriteTask(
            comic_pks=frozenset(batch.keys()),
            per_comic_patches=dict(batch),
            mode=state.mode,
            formats=state.formats,
            delete_original=state.delete_original,
        )
        self.librarian_queue.put(write_task)
        count = len(batch)
        self.log.info(
            f"Online tag: fetched {count} comics by stored id, skipping their search."
        )

    def _prefetch_stored_ids(
        self,
        state: SessionState,
        comic_paths: dict[int, Path],
        task: BulkOnlineTagTask,
        credentials: OnlineCredentials,
    ) -> None:
        """
        Resolve comics with a stored issue id by explicit id before searching.

        Fetches each already-identified comic in one API call, writes the tags
        through the same ``BulkTagWriteTask`` path the scan uses, and drops it
        from ``comic_paths`` so the search session only handles the rest.
        Skipped on dry runs and for sources without credentials.
        """
        if task.dry_run:
            return
        usable_sources = tuple(
            source
            for source in task.sources
            if self._source_has_credentials(credentials, source)
        )
        id_map = build_stored_id_map(comic_paths.keys(), usable_sources)
        if not id_map:
            return

        batch: dict[int, dict] = {}
        for pk, source_ids in id_map.items():
            path = comic_paths[pk]
            result = self._fetch_stored_id(
                path, source_ids, credentials, merge_all_sources=task.merge_all_sources
            )
            if result is None:
                continue
            primary_source, tags = result
            batch[pk] = tags
            state.stats.written_paths.add(path)
            state.stats.matched_source_by_path.setdefault(path, []).append(
                primary_source
            )

        if batch:
            self._commit_prefetch(state, comic_paths, batch)

    def run_session(self, task: BulkOnlineTagTask) -> None:
        """Execute a non-blocking online tagging scan (Pass 1 only)."""
        # Read-only libraries are excluded at the API funnel; backstop here too.
        comics = (
            Comic.objects.filter(pk__in=task.comic_pks)
            .exclude(library__read_only=True)
            .only("pk", "path")
        )
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
            # first_wins=False queries every source per comic and merges.
            first_wins=not task.merge_all_sources,
            on_event=self._on_event,
            prompt_handler=CodexPromptHandler(),
        )
        state = SessionState(
            session=session,
            path_to_pk={path: pk for pk, path in comic_paths.items()},
            mode="update",
            match_mode=task.mode,
            sources=tuple(task.sources),
            merge_all_sources=task.merge_all_sources,
            formats=tuple(defaults.default_formats),
            delete_original=task.delete_original,
            total_comics=0,
            completed_comics=0,
            # Everything needed to rebuild a resume task over the comics this
            # scan never reaches (comic_pks + session_id are regenerated then).
            resume_params={
                "sources": list(task.sources),
                "mode": task.mode,
                "prompts_mode": task.prompts_mode,
                "effort": task.effort,
                "auto_threshold": task.auto_threshold,
                "delete_original": task.delete_original,
                "merge_all_sources": task.merge_all_sources,
                "dry_run": task.dry_run,
            },
        )
        self._active_session_id = task.session_id
        with self._lock:
            self._sessions[task.session_id] = state
        set_active_scan_id(task.session_id)
        # A fresh batch starts with a clean resolution record and resume
        # descriptor so a prior batch's user_matched/user_skipped overlays —
        # and any leftover paused remainder — don't bleed onto these comics.
        clear_resolved_outcomes()
        clear_resume_state()

        start = monotonic()
        try:
            # Fast path: comics codex already has an issue id for are fetched
            # directly by that id (one API call each) and dropped from the set,
            # so the search pass below only handles the unidentified remainder.
            self._prefetch_stored_ids(state, comic_paths, task, credentials)
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
            # Freeze the final tally in the snapshot (active=False) so the
            # status table keeps showing how the batch resolved until the next
            # scan starts — published before clearing the active session id so
            # it still carries this scan's id.
            self._publish_snapshot(
                state, active=False, force=True, session_id=task.session_id
            )
            with self._lock:
                self._sessions.pop(task.session_id, None)
            self._active_session_id = None
            set_active_scan_id("")
            # Apply any answers the admin gave mid-scan now that the thread
            # is free. The cache entries were already removed inline; each
            # apply builds its own fresh session, so it's independent of
            # this (possibly crashed) scan's session.
            self._apply_deferred_resolutions(state)

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

    def dismiss_session(self) -> None:
        """
        Clear the status-table snapshot and resume descriptor.

        For dismissing a paused/finished session from the admin table. Pending
        prompts and any live scan are deliberately left untouched.
        """
        clear_snapshot()
        clear_resume_state()
        self.log.info("Online tag: dismissed session snapshot.")

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
        pk = prompt.get("pk")
        if action == "skip":
            record_resolution(pk, USER_SKIPPED)
            self.log.info(f"Online tag: skipped prompt for {prompt.get('path')!r}.")
            return
        # Recorded as user-matched up front; if the apply drifts it re-queues a
        # fresh prompt, which the read-time overlay shows as needs-review again
        # (the live prompt set wins over the recorded outcome).
        record_resolution(pk, USER_MATCHED)
        self._apply_resolution(prompt, action, payload, chosen_volume_id)

    def skip_all_prompts(self) -> int:
        """Drop every pending prompt. Returns the number skipped."""
        prompts = get_pending_prompts()
        count = len(prompts)
        if count:
            for prompt in prompts.values():
                record_resolution(prompt.get("pk"), USER_SKIPPED)
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
        # A concrete pick (a candidate with a known issue id) is fetched
        # directly by id — never re-searched. A re-search replay drifts under
        # rate limiting (a different candidate set misses the preloaded
        # fingerprint), which would silently discard the admin's choice and
        # re-queue a fresh, often worse, prompt. Direct id fetch is immune.
        explicit = self._explicit_issue_id(action, payload, source)
        if explicit is not None:
            self._apply_explicit_id(prompt, pk, explicit, path_str, credentials)
            return
        # defer_prompts on: the bridged selector consults the preloaded
        # resolution; without it (or a handler) an ambiguous re-search would
        # fall through to comicbox's interactive CLI prompt inside the daemon.
        session = OnlineSession(
            sources=(source,),
            credentials=credentials,
            mode=MatchMode(prompt.get("mode") or "auto"),
            defer_prompts=True,
        )
        session.preload_resolution(
            prompt["fingerprint"],
            action=cast("Literal['choose', 'skip', 'manual']", action),
            payload=payload,
            chosen_volume_id=chosen_volume_id,
        )
        tags = self._first_tags(session, Path(path_str))
        if not tags:
            self._handle_unresolved(prompt, path_str, session)
            return
        self._enqueue_resolved_write(prompt, pk, tags, path_str)

    @staticmethod
    def _explicit_issue_id(
        action: str, payload: Any, default_source: str
    ) -> tuple[str, int] | None:
        """Parse a ``manual`` ``source:issue_id`` payload into (source, id)."""
        if action != "manual" or not isinstance(payload, str):
            return None
        src, sep, id_str = payload.partition(":")
        if not sep:
            return None
        try:
            issue_id = int(id_str)
        except (TypeError, ValueError):
            return None
        return (src or default_source), issue_id

    def _apply_explicit_id(
        self,
        prompt: dict[str, Any],
        pk: int,
        explicit: tuple[str, int],
        path_str: str,
        credentials: OnlineCredentials,
    ) -> None:
        """Fetch the picked issue by id and enqueue its write (no re-search)."""
        src, issue_id = explicit
        tags = fetch_tags_by_explicit_id(Path(path_str), src, issue_id, credentials)
        if tags:
            self._enqueue_resolved_write(prompt, pk, tags, path_str)
        else:
            # The id itself didn't resolve (wrong/unknown issue). Don't re-queue
            # a fresh ambiguous prompt — the admin made an explicit choice.
            msg = f"chosen issue {src}:{issue_id} did not resolve for {path_str}"
            self.log.warning(f"Online tag: {msg}.")

    def _handle_unresolved(
        self, prompt: dict[str, Any], path_str: str, session: OnlineSession
    ) -> None:
        """Log the dead resolution, re-queueing a fresh prompt if it drifted."""
        if self._repersist_drifted_prompt(prompt, session):
            self.log.warning(
                f"Online tag: prompt for {path_str} drifted; queued a fresh one."
            )
        else:
            self.log.warning(f"Online tag: no tags resolved for {path_str}.")

    def _enqueue_resolved_write(
        self, prompt: dict[str, Any], pk: int, tags: dict[str, Any], path_str: str
    ) -> None:
        """Queue the write for a successfully resolved prompt match."""
        write_task = BulkTagWriteTask(
            comic_pks=frozenset({pk}),
            per_comic_patches={pk: tags},
            mode="update",
            formats=tuple(prompt.get("formats") or ("COMIC_INFO",)),
            delete_original=bool(prompt.get("delete_original")),
        )
        self.librarian_queue.put(write_task)
        self.log.info(f"Online tag: applied resolved match for {path_str}.")

    def _repersist_drifted_prompt(
        self, prompt: dict[str, Any], session: OnlineSession
    ) -> bool:
        """
        Re-queue the prompt when the replayed search no longer matches it.

        The deferred-prompt fingerprint embeds the candidate-id set, so a
        re-search returning a different candidate list (source data changed,
        a rate-limited series dropped out) misses the preloaded resolution
        and defers a fresh prompt instead. Persist that fresh prompt — same
        comic, new fingerprint and candidates — so the admin can answer
        again instead of the click dying silently.
        """
        pk = prompt.get("pk")
        if pk is None:
            return False
        formats = tuple(prompt.get("formats") or ("COMIC_INFO",))
        delete_original = bool(prompt.get("delete_original"))
        new = {
            dp.fingerprint: self._serialize_prompt(
                dp, pk, formats, delete_original=delete_original
            )
            for dp in session.deferred_prompts()
        }
        if not new:
            return False
        add_pending_prompts(new)
        self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)
        return True

    @staticmethod
    def _first_tags(session: OnlineSession, path: Path) -> dict[str, Any] | None:
        """Return the tags from the single re-tagged comic, or None."""
        for result in session.tag_many([path]):
            # Unmatched results still carry the comic's merged existing
            # metadata; writing that would re-write the file with no new
            # information.
            if result.matched and result.tags and not result.error:
                return result.tags
            break
        return None

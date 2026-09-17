"""
Manage online tagging sessions and their lifecycle.

A tagging *scan* (``run_session``) is non-blocking: it auto-matches and
writes the confident comics in one pass, persists any ambiguous matches as
deferred *prompts* in the cache, then finishes and releases the thread. The
prompts linger until an admin answers them.

Comicbox fingerprints a deferred prompt at series level, so one prompt is one
*question* and usually stands for several comics — every issue of that series
in the batch. ``resolve_prompt`` takes the admin's answer and hands it to
:mod:`~codex.librarian.onlinetag.prompt_apply`, which writes it to all of
them. That runs decoupled from the scan that asked, because the fingerprint is
deterministic across processes; when a scan is still running, the answer is
also preloaded into its live session so the rest of the series never has to
ask again.
"""

from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any

from comicbox.config.online import resolve_effort
from comicbox.events import (
    AutoWritten,
    Event,
    FileError,
    FileFinished,
    NoMatch,
    PromptDeferred,
    RateLimited,
    SearchCompleted,
    Skipped,
    SourceStarted,
)
from comicbox.exceptions import ComicboxError
from comicbox.online_session import (
    Effort,
    MatchMode,
    OnlineCredentials,
    OnlineSession,
)
from django.utils.timezone import now, timedelta
from humanize import naturaldelta

from codex.librarian.notifier.tasks import (
    ONLINE_TAG_PROMPT_TASK,
    ONLINE_TAG_SNAPSHOT_TASK,
)
from codex.librarian.onlinetag.estimate import estimate_seconds
from codex.librarian.onlinetag.explicit_id import (
    fetch_tags_by_explicit_id,
    resolved_id_sources,
)
from codex.librarian.onlinetag.prompt_apply import PromptApplier
from codex.librarian.onlinetag.session_cache import (
    add_pending_prompts,
    get_pending_prompts,
    prompt_comics,
    remove_pending_prompt,
    set_active_scan_id,
    set_pending_prompts,
)
from codex.librarian.onlinetag.session_snapshot import (
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
    serialize_prompt,
)
from codex.librarian.onlinetag.statuses import USER_MATCHED, USER_SKIPPED
from codex.librarian.onlinetag.stored_id_prepass import build_stored_id_map
from codex.librarian.onlinetag.tag_pass_runner import TagPassRunner
from codex.librarian.onlinetag.tasks import (
    BulkOnlineTagTask,
    OnlineTagAbortTask,
    OnlineTagPromptResponseTask,
    OnlineTagSkipAllPromptsTask,
)
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.librarian.status_controller import StatusController
from codex.models.admin import ComicboxTaggingDefaults
from codex.models.comic import Comic
from codex.settings import COMICBOX_ONLINE_CONFIG


def _online_config(effort: str) -> ComicboxSettings:
    """
    Codex's online settings with this scan's effort applied.

    Effort is not an ``OnlineSession`` keyword — it lives in the settings
    tree the session layers its own preferences over, which is what the
    ``config`` keyword is for.

    An empty effort is left empty rather than spelled out as the value it
    resolves to. Comicbox reads any named effort as a decision and leaves
    it alone; it is only free to drop a large unattended run to minimal,
    and spare it hours of Comic Vine rate limiting, while nobody has
    named one.
    """
    if not effort:
        return COMICBOX_ONLINE_CONFIG
    online = COMICBOX_ONLINE_CONFIG.online
    tuning = replace(online.tuning, effort=Effort(effort))
    return replace(COMICBOX_ONLINE_CONFIG, online=replace(online, tuning=tuning))


if TYPE_CHECKING:
    from multiprocessing import Queue

    from comicbox.config.settings import ComicboxSettings
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
        # The live-lookup publish rides its own clock and its own dedupe so a
        # burst of them can neither starve the result-boundary publish (which
        # carries the terminal outcome and the resume descriptor) nor hammer
        # the cache on a warm-HTTP-cache run, where comicbox answers a search
        # from local disk and nothing paces the event stream.
        self._last_live_publish: float = 0.0
        self._last_live_key: tuple[Path | None, str] | None = None
        self._pass_runner = TagPassRunner(
            log,
            librarian_queue,
            self.status_controller,
            self._drain_thread_queue,
            self._publish_snapshot,
        )
        # Answering a prompt is decoupled from the scan that raised it, so
        # the machinery that writes an answer lives in its own module.
        self._prompt_applier = PromptApplier(
            log, librarian_queue, self._build_credentials
        )

    def _build_credentials(self) -> OnlineCredentials | None:
        """Load and decrypt credentials from the defaults model."""
        try:
            defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        except ComicboxTaggingDefaults.DoesNotExist:
            return None
        if (
            not defaults.metron_key
            and not defaults.metron_user
            and not defaults.comicvine_key
        ):
            return None
        return OnlineCredentials(
            metron_key=defaults.metron_key or "",
            metron_user=defaults.metron_user or "",
            metron_password=defaults.metron_password or "",
            comicvine_key=defaults.comicvine_key or "",
            comicvine_url=defaults.comicvine_url or "",
        )

    @staticmethod
    def _source_has_credentials(credentials: OnlineCredentials, source: str) -> bool:
        """Whether ``credentials`` actually carries auth for ``source``."""
        if source == "metron":
            return bool(
                credentials.metron_key
                or (credentials.metron_user and credentials.metron_password)
            )
        if source == "comicvine":
            return bool(credentials.comicvine_key)
        return False

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
        write_resume: bool = True,
        touch_throttle: bool = True,
    ) -> None:
        """Fold scan state into the cache snapshot the admin status table reads."""
        try:
            if not force and monotonic() - self._last_publish < self._PUBLISH_DELTA:
                return
            if touch_throttle:
                self._last_publish = monotonic()
            self._store_snapshot(state, session_id, active=active)
            if write_resume:
                self._store_resume(state)
        except Exception:
            self.log.exception("Publishing online tag session snapshot")

    def _store_snapshot(
        self, state: SessionState, session_id: str | None, *, active: bool
    ) -> None:
        """Build, cache, and announce one snapshot."""
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
        # Announce from the one place that writes it, so every published
        # snapshot is followed by exactly one notification and never the
        # reverse order — the client fetches in response to this.
        self.librarian_queue.put(ONLINE_TAG_SNAPSHOT_TASK)

    def _store_resume(self, state: SessionState) -> None:
        """
        Persist the uncapped remainder + original params.

        So a kill or pause can resume what this scan never reached. A normal
        finish leaves nothing remaining, which clears the key (not resumable).
        """
        review_pks = {
            comic["pk"]
            for prompt in get_pending_prompts().values()
            for comic in prompt_comics(prompt)
        }
        set_resume_state(state.resume_params, remaining_pks(state, review_pks))

    # The live-lookup publish's own floor. comicbox serves a search from its
    # on-disk HTTP cache (7 day TTL, persisted under /config) whenever it can,
    # so on a re-scan the events fire at CPU speed with no network to pace
    # them. Well under the ~6-20s of a cold lookup, so it never costs a frame
    # that mattered.
    _LIVE_PUBLISH_DELTA = 1.0

    def _publish_live(self, state: SessionState) -> None:
        """
        Publish + announce the "looking up" marker the status table renders.

        Guarded, like the publish it wraps: this runs inside comicbox's event
        dispatch, which forwards to the handler with no try of its own, and
        the emit sits *before* the lookup's own try — so an exception escaping
        here would surface as a FileError and mark the comic errored in every
        column. A status display must never be able to corrupt an outcome.
        """
        try:
            key = (state.live.path, state.live.source)
            if key == self._last_live_key:
                return
            now_mono = monotonic()
            if now_mono - self._last_live_publish < self._LIVE_PUBLISH_DELTA:
                return
            self._last_live_key = key
            self._last_live_publish = now_mono
            # Never stamps the shared throttle: doing so would suppress the
            # unforced result-boundary publish that carries the comic's
            # terminal status and narrows the resume descriptor. The remainder
            # can only shrink between here and that publish, which rewrites
            # it, so skipping the resume write costs at most one comic of
            # staleness and saves a second file write per lookup.
            self._publish_snapshot(
                state, force=True, write_resume=False, touch_throttle=False
            )
            self._mark_looking_up(state.live.source)
        except Exception:
            self.log.exception("Publishing online tag live lookup")

    def _mark_looking_up(self, source: str) -> None:
        """
        Move the librarian status rail in step with the live marker.

        The status table has its own notification and redraws the moment a
        source starts on a comic. The rail renders the LibrarianStatus row,
        which only moves when a comic *completes* — a minute of apparent
        silence per comic while a lookup is plainly running. Naming the
        source being consulted gives the rail the same heartbeat, paced by
        the live publish's own floor.
        """
        status = self._pass_runner.lookup_status
        if not status or not source:
            return
        status.subtitle = f"looking up on {source}"
        self.status_controller.update(status, force=True)

    def _on_event(self, event: Event) -> None:
        """Handle comicbox online events."""
        state = self._active_state()
        if state is not None:
            state.stats.record(event)
            self._track_live_lookup(state, event)
        match event:
            case RateLimited():
                self._pass_runner.rate_limited = True
                lookup_status = self._pass_runner.lookup_status
                if lookup_status:
                    self._mark_rate_limited(lookup_status, state, event)
            # A source that reported an outcome just completed a request, so
            # whatever wait it was serving is provably over. Deadlines expire
            # on their own epoch anyway; this releases one early rather than
            # leaving the strip counting down against a source already back at
            # work. SearchStarted is deliberately absent — it fires *before*
            # the request, which is exactly when a rate limit is hit.
            case (
                SearchCompleted(source=source)
                | AutoWritten(source=source)
                | NoMatch(source=source)
                | Skipped(source=source)
            ) if source:
                self._pass_runner.source_retry_at.pop(source, None)
            case PromptDeferred() if state is not None:
                self._persist_prompts(state)
            case _:
                pass

    def _track_live_lookup(self, state: SessionState, event: Event) -> None:
        """Follow what the scan is consulting right now, and publish it."""
        match event:
            # SourceStarted covers every route a source can take,
            # including the fast paths a search never reaches.
            case SourceStarted(path=path, source=source) if path and source:
                state.live.begin(path, source)
                self._publish_live(state)
            # The comic is done; nothing is live until the next source starts.
            # No publish — the result boundary is microseconds away.
            case FileFinished(path=path) | FileError(path=path) if path:
                state.live.end(path)
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
            # No delay means the retry budget is spent: the source has stopped
            # waiting and given up, so drop its countdown instead of leaving
            # the strip claiming a retry that will never come.
            status.retry_at = None
            if event.source:
                self._pass_runner.source_retry_at.pop(event.source, None)
        # Push the completion estimate out by the wait plus the work still
        # left, so the total countdown doesn't sail past zero while stalled.
        remaining = (
            max(0, state.total_comics - state.completed_comics)
            if state is not None
            else 0
        )
        work = (
            estimate_seconds(
                remaining,
                state.sources,
                effort=state.effort,
                merge_all_sources=state.merge_all_sources,
            )
            if state is not None
            else 0.0
        )
        total = secs + work
        status.eta = now() + timedelta(seconds=total) if total else None
        # A rate limit is a state change, not a progress tick: forced past
        # the controller's coalescing window rather than reaching in to
        # backdate the status's own clock.
        self.status_controller.update(status, notify=True, force=True)
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

    @staticmethod
    def _record_prompt_outcome(
        state: SessionState, prompt: dict[str, Any], status: str
    ) -> int:
        """Record one answer against every comic it speaks for; return how many."""
        source = prompt.get("source")
        comics = prompt_comics(prompt)
        for comic in comics:
            state.answered_pks.add(comic["pk"])
            record_resolution(comic["pk"], status, source)
        return len(comics)

    def _preload_mid_scan_answer(
        self, state: SessionState, item: OnlineTagPromptResponseTask
    ) -> None:
        """
        Hand the answer to the running session so the rest of the series takes it.

        This is the half of comicbox's deferred-prompt contract codex never
        held up: the fingerprint is series-level precisely so a preloaded
        resolution auto-applies to every later issue of that series
        (``_lookup_cached_prompt`` re-maps the pick onto whichever candidate
        carries the chosen volume). Without it the later issues re-deferred
        the same question and were dropped as already-answered.

        Only a ``choose`` that named a volume can transfer: the candidates
        were scored for one issue, so an index or a bare issue id means
        nothing to the next issue. Those comics ask again on their own.
        """
        if item.action != "choose" or item.chosen_volume_id is None:
            return
        state.session.preload_resolution(
            item.prompt_fingerprint,
            action="choose",
            payload=item.payload,
            chosen_volume_id=item.chosen_volume_id,
        )

    def _defer_prompt_response(
        self, state: SessionState, item: OnlineTagPromptResponseTask
    ) -> None:
        """Drop one answered prompt from the cache now; defer the apply."""
        fingerprint = item.prompt_fingerprint
        prompt = get_pending_prompts().get(fingerprint)
        if not prompt:
            return
        remove_pending_prompt(fingerprint)
        self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)
        if item.action == "skip":
            count = self._record_prompt_outcome(state, prompt, USER_SKIPPED)
            path = prompt.get("path")
            self.log.info(
                f"Online tag: skipped prompt for {count} comic(s) mid-scan ({path!r})."
            )
            return
        self._record_prompt_outcome(state, prompt, USER_MATCHED)
        self._preload_mid_scan_answer(state, item)
        state.deferred_applies.append(
            (prompt, item.action, item.payload, item.chosen_volume_id)
        )

    def _defer_skip_all(self, state: SessionState) -> None:
        """Clear every pending prompt now; mark them answered for this scan."""
        prompts = get_pending_prompts()
        if not prompts:
            return
        for prompt in prompts.values():
            self._record_prompt_outcome(state, prompt, USER_SKIPPED)
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
                self._prompt_applier.apply(prompt, action, payload, chosen_volume_id)
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
            # ``path_to_pk`` is keyed by path; its *values* are pks, which a
            # Path never equals, so testing them admitted every comic twice.
            if path not in state.path_to_pk:
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

    def _group_deferred_prompts(self, state: SessionState) -> dict[str, dict[str, Any]]:
        """
        Collect the scan's deferred prompts into one entry per question.

        Every issue of a series shares a fingerprint, so the deferrals
        collapse into a single prompt carrying every comic that raised it.
        Serializing each deferral under its own fingerprint key — which is
        what this used to do — kept only the last comic of the series and
        silently lost the rest.
        """
        grouped: dict[str, dict[str, Any]] = {}
        for dp in state.session.deferred_prompts():
            if dp.path is None:
                continue
            pk = state.path_to_pk.get(dp.path)
            # Don't resurrect a comic the admin already answered for mid-scan.
            # Keyed by comic rather than by fingerprint: a later issue of an
            # already-answered series is a question nobody has answered yet.
            if pk is None or pk in state.answered_pks:
                continue
            comic = {"pk": pk, "path": str(dp.path)}
            prompt = grouped.get(dp.fingerprint)
            if prompt is None:
                grouped[dp.fingerprint] = serialize_prompt(
                    dp,
                    [comic],
                    state.formats,
                    delete_original=state.delete_original,
                    rename=state.rename,
                )
            elif all(known["pk"] != pk for known in prompt["comics"]):
                prompt["comics"].append(comic)
        return grouped

    def _persist_prompts(self, state: SessionState) -> None:
        """Merge the scan's current deferred prompts into the cache and notify."""
        if new := self._group_deferred_prompts(state):
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
    ) -> tuple[tuple[str, ...], dict] | None:
        """
        Fetch one already-identified comic by its stored ids.

        Returns ``(resolved_sources, tags)`` on success, or ``None`` when the
        primary id didn't resolve or the fetch errored — the caller leaves such
        a comic to the search pass. Under ``merge_all_sources`` the comic's
        other stored ids are fetched and merged onto the primary record, and
        each one that lands is reported: a merged fetch is every contributing
        source's match, not only the primary's.
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
        except (ComicboxError, OSError) as exc:
            self.log.warning(f"Online tag stored-id prefetch failed for {path}: {exc}")
            return None
        if not tags:
            return None
        # The primary is proven by the fetch itself, which returns nothing
        # unless its own id came back. Each extra has to show its id in the
        # merged record: an extra that didn't resolve contributed nothing.
        extras = resolved_id_sources(tags, dict(extra_ids))
        return (primary_source, *extras), tags

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
            rename=state.rename,
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
        Skipped for sources without credentials.
        """
        usable_sources = tuple(
            source
            for source in task.sources
            if self._source_has_credentials(credentials, source)
        )
        id_map = build_stored_id_map(comic_paths.keys(), usable_sources)
        if not id_map:
            return

        # Opened here rather than in the search pass: on a re-tag every comic
        # resolves in this loop, and a scan whose whole runtime is the prepass
        # showed the admin an empty status rail. Totalled over the batch, not
        # the id map, so the count doesn't jump when the search pass adopts it.
        status = self._pass_runner.begin_status(len(comic_paths))
        batch: dict[int, dict] = {}
        for pk, source_ids in id_map.items():
            path = comic_paths[pk]
            # The prepass fetches outside the event-emitting session, so codex
            # is the only thing that knows a lookup is happening at all —
            # without this the table sits on the *previous* session's rows for
            # the whole prepass, which on a re-tag is most of the run.
            state.live.begin(path, next(iter(source_ids)))
            self._publish_live(state)
            result = self._fetch_stored_id(
                path, source_ids, credentials, merge_all_sources=task.merge_all_sources
            )
            state.live.end(path)
            if result is None:
                continue
            sources, tags = result
            batch[pk] = tags
            state.stats.record_prefetch_match(path, sources)
            # The rail's own progress: the prepass is the whole run on a
            # re-tag, and its comics are the ones the search pass never sees.
            status.complete = len(batch)
            self.status_controller.update(status)

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
        online_config = _online_config(task.effort)
        session = OnlineSession(
            sources=task.sources,
            # Pinned sources fetch their issue id directly; the rest search.
            ids=dict(task.ids),
            credentials=credentials,
            match=MatchMode(task.mode),
            defer_prompts=defer_prompts,
            # first_wins=False queries every source per comic and merges.
            first_wins=not task.merge_all_sources,
            on_event=self._on_event,
            prompt_handler=CodexPromptHandler(),
            # Codex's own online settings, chiefly the cache directory
            # under /config. Without them the session reads its own and
            # comicbox's sqlite caches land somewhere a container
            # recreation throws away.
            config=online_config,
        )
        state = SessionState(
            session=session,
            path_to_pk={path: pk for pk, path in comic_paths.items()},
            mode="update",
            match_mode=task.mode,
            sources=tuple(task.sources),
            # What the estimate is priced at: whatever the settings this
            # session was handed resolve to, so an unset effort and a
            # per-source override both reach it.
            effort=resolve_effort(online_config.online, "comicvine").value,
            merge_all_sources=task.merge_all_sources,
            formats=tuple(defaults.default_formats),
            delete_original=task.delete_original,
            rename=task.rename,
            total_comics=0,
            completed_comics=0,
            # Everything needed to rebuild a resume task over the comics this
            # scan never reaches (comic_pks + session_id are regenerated then).
            resume_params={
                "sources": list(task.sources),
                "mode": task.mode,
                "effort": task.effort,
                "prompts_mode": task.prompts_mode,
                "delete_original": task.delete_original,
                "merge_all_sources": task.merge_all_sources,
                "rename": task.rename,
                "ids": dict(task.ids),
            },
        )
        self._active_session_id = task.session_id
        with self._lock:
            self._sessions[task.session_id] = state
        set_active_scan_id(task.session_id)
        # A fresh batch starts with a clean resolution record so a prior
        # batch's user_matched/user_skipped overlays don't bleed onto these
        # comics.
        clear_resolved_outcomes()
        # A Resume re-runs the same paths, so the previous scan's last live
        # key could otherwise dedupe this one's first publish away.
        self._last_live_key = None
        self._last_live_publish = 0.0
        # Record this batch's remainder up front rather than merely clearing
        # the prior one (which overwriting does anyway). Publishing narrows it
        # as comics finish, but the first publish is throttled and a daemon
        # killed before it would otherwise leave the batch with no descriptor
        # at all — unresumable, while the frozen snapshot still shows every
        # comic queued.
        set_resume_state(state.resume_params, list(state.path_to_pk.values()))

        start = monotonic()
        try:
            # Fast path: comics codex already has an issue id for are fetched
            # directly by that id (one API call each) and dropped from the set,
            # so the search pass below only handles the unidentified remainder.
            # Skipped when the request pinned ids: the prepass would drop that
            # single comic out of the session entirely, but the pinned sources
            # must be fetched *and* the unpinned ones searched in one lookup so
            # merge_all_sources can merge both results.
            if not task.ids:
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
            # it still carries this scan's id. The marker goes first: a scan
            # that died by raising is still holding one, and a frozen snapshot
            # must not claim a lookup is running.
            state.live.clear()
            # No-op unless the prepass raised before the search pass could
            # adopt (and finish) the status row it opened.
            self._pass_runner.finish_status()
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
            # A pause taken during a rate-limit sleep aborts the retry with no
            # FileFinished behind it, so nothing else would clear the marker.
            state.live.clear()
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
        source = prompt.get("source")
        comics = prompt_comics(prompt)
        if action == "skip":
            for comic in comics:
                record_resolution(comic["pk"], USER_SKIPPED, source)
            path = prompt.get("path")
            self.log.info(
                f"Online tag: skipped prompt for {len(comics)} comic(s) ({path!r})."
            )
            return
        # Recorded as user-matched up front; if the apply drifts it re-queues a
        # fresh prompt, which the read-time overlay shows as needs-review again
        # (the live prompt set wins over the recorded outcome).
        for comic in comics:
            record_resolution(comic["pk"], USER_MATCHED, source)
        self._prompt_applier.apply(prompt, action, payload, chosen_volume_id)

    def skip_all_prompts(self) -> int:
        """Drop every pending prompt. Returns the number skipped."""
        prompts = get_pending_prompts()
        count = len(prompts)
        if count:
            for prompt in prompts.values():
                source = prompt.get("source")
                for comic in prompt_comics(prompt):
                    record_resolution(comic["pk"], USER_SKIPPED, source)
            set_pending_prompts({})
            self.librarian_queue.put(ONLINE_TAG_PROMPT_TASK)
        self.log.info(f"Online tag: skipped {count} prompt(s).")
        return count

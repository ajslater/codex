"""
A live, JSON-safe snapshot of the in-flight online tagging scan.

The scan's authoritative state (:class:`~codex.librarian.onlinetag.session_state.SessionState`)
lives only in the ``OnlineTagThread`` daemon process; Django request handlers
cannot reach it. This module bridges that gap: the daemon folds the scan's
:class:`~codex.librarian.onlinetag.outcome_stats.OnlineTagOutcomeStats` plus the
pending-prompt cache into one snapshot dict and stores it in the dedicated
``tagging`` cache, so the admin Tagging tab can render a live status table by
reading a single key.

Design notes:

- **Terminal per-comic status is derived, liveness is tracked.**
  ``OnlineTagOutcomeStats`` already records every comic's path in
  ``written_paths`` / ``no_change_paths`` / ``errored_paths`` /
  ``matched_source_by_path``; "needs review" comes from the pending-prompt
  cache (keyed by pk). The single *in-flight* comic is not guessed from list
  order — comicbox re-sorts the batch by series fingerprint — but read from
  ``SessionState.live``, the marker the daemon sets from the event stream. No
  marker means nothing is in flight, which is the honest reading between
  comics and after a cancel.
- **The comic list is capped** (``_MAX_COMIC_ROWS``) so a batch of thousands
  doesn't bloat the cache or the wire. Actionable rows (in-flight, needs
  review, error) and upcoming (queued) come first; finished rows fill the rest.
  ``comic_count`` always carries the true total so the UI can say "showing N
  of M".
- **Each row also carries per-source cells** (``source_statuses``): what each
  source did with that comic, which the status table renders as one column per
  source. The terminal ones come from the fold; the two live states are
  projected here onto the in-flight row alone, because both live on the scan
  rather than in the event history — ``in_flight`` ("Looking up") from
  ``SessionState.live``, and ``waiting`` from the per-source retry deadlines.
- **Status string values are deliberately snake_case** and pass through the
  camelCase API renderer untouched (it only camelizes dict *keys*); the
  frontend matches on these literals. They are defined in
  :mod:`~codex.librarian.onlinetag.statuses` and re-exported here.
- Lives in ``caches["tagging"]`` like the prompts/scan-id state, with no TTL.
  The active flag flips to False when the scan finishes so the final tally
  stays visible until the next batch starts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from codex.cache import tagging_cache as cache
from codex.librarian.onlinetag.estimate import SOURCE_RATE_PER_MINUTE
from codex.librarian.onlinetag.session_cache import get_pending_prompts

# Re-exported so callers can keep reading the status vocabulary off the module
# that renders it.
from codex.librarian.onlinetag.statuses import (
    ACTIONABLE,
    ERROR,
    FINISHED,
    IN_FLIGHT,
    LIVE_SOURCE_STATUSES,
    MATCHED,
    NEEDS_REVIEW,
    NO_MATCH,
    QUEUED,
    USER_MATCHED,
    WAITING,
)

if TYPE_CHECKING:
    from pathlib import Path

    from codex.librarian.onlinetag.session_state import SessionState

_SNAPSHOT_KEY = "onlinetag:session_snapshot"
_NO_TIMEOUT = None
_MAX_COMIC_ROWS: Final = 500

_RESOLVED_KEY = "onlinetag:resolved_outcomes"
_RESUME_KEY = "onlinetag:resume_state"


def get_snapshot() -> dict[str, Any] | None:
    """Return the stored session snapshot, or None."""
    return cache.get(_SNAPSHOT_KEY) or None


def set_snapshot(snapshot: dict[str, Any]) -> None:
    """Persist the session snapshot with no TTL."""
    cache.set(_SNAPSHOT_KEY, snapshot, timeout=_NO_TIMEOUT)


def clear_snapshot() -> None:
    """Drop the session snapshot entirely."""
    cache.delete(_SNAPSHOT_KEY)


def deactivate_snapshot() -> None:
    """
    Mark a lingering snapshot inactive without dropping it.

    An ``active`` snapshot left by a scan that the daemon can no longer be
    running (process restart, or the janitor finding no live session) would
    otherwise read as "scanning" forever. Flipping the flag keeps the final
    tally visible while making clear nothing is in flight.

    A crash skips ``run_session``'s ``finally``, so the last throttled
    snapshot can still carry an ``in_flight`` row — dishonest once no scan is
    running. Demote it to ``queued`` (the batch tally already counts in-flight
    as queued, so no count changes) so the comic reads as still-to-do, which
    is also exactly what Resume will re-run. Per-source cells claiming a live
    lookup or a rate-limit wait go the same way.

    Deliberately *not* guarded on ``active``. A scan that dies by raising
    freezes the snapshot through ``run_session``'s ``finally`` with
    ``active`` already False but its live row intact, and a snapshot written
    by an older Codex can carry one too — the tagging cache is file-backed
    with no TTL, so it outlives the upgrade. Guarding on ``active`` made both
    unrepairable forever.
    """
    snapshot = get_snapshot()
    if not snapshot:
        return
    dirty = bool(snapshot.get("active"))
    snapshot["active"] = False
    for comic in snapshot.get("comics") or []:
        if comic.get("status") == IN_FLIGHT:
            comic["status"] = QUEUED
            dirty = True
        dirty = _drop_live_source_statuses(comic) or dirty
    dirty = _drop_rate_limits(snapshot) or dirty
    if dirty:
        set_snapshot(snapshot)


def _drop_live_source_statuses(comic: dict[str, Any]) -> bool:
    """Strip a row's searching/waiting cells; True if any were there."""
    cells = comic.get("source_statuses")
    if not cells:
        return False
    dropped = False
    for source, status in tuple(cells.items()):
        if status in LIVE_SOURCE_STATUSES:
            del cells[source]
            dropped = True
    return dropped


def _drop_rate_limits(snapshot: dict[str, Any]) -> bool:
    """
    Disarm the sources strip's retry countdowns.

    A crash skips the pass runner's ``finally``, so a scan killed mid-wait can
    freeze a retry deadline that is still in the future — leaving the strip
    counting down, then stuck on "retrying…", for a scan that is not running.

    Returns whether anything was actually armed, so an already-clean snapshot
    isn't rewritten on every daemon start and janitor sweep.
    """
    disarmed = False
    for source in snapshot.get("sources") or []:
        if source.get("rate_limited") or source.get("retry_at_epoch") is not None:
            disarmed = True
        source["rate_limited"] = False
        source["retry_at_epoch"] = None
    return disarmed


# --- resolution outcomes -----------------------------------------------------
#
# A scan freezes its snapshot when it finishes, but the admin can keep
# answering deferred prompts afterward — so a comic the snapshot recorded as
# "needs review" may since have been picked or skipped. We record each
# resolution (keyed by comic pk) here and overlay it at read time, which both
# corrects the stale status and surfaces that a human was involved. Cleared
# when a new scan starts; pruned for vanished comics by the janitor.


def get_resolved_outcomes() -> dict[int, Any]:
    """Return the {pk: {status, sources}} resolution record."""
    return cache.get(_RESOLVED_KEY, {}) or {}


def set_resolved_outcomes(outcomes: dict[int, Any]) -> None:
    """Replace the resolution record, or clear it when empty."""
    if outcomes:
        cache.set(_RESOLVED_KEY, outcomes, timeout=_NO_TIMEOUT)
    else:
        cache.delete(_RESOLVED_KEY)


def _normalize_resolution(value: Any) -> dict[str, Any]:
    """
    Read one resolution record as {status, sources}.

    Records written before per-source columns are bare status strings; the
    file-backed cache outlives an upgrade, so they still have to overlay —
    just without a source to attribute them to.
    """
    if isinstance(value, str):
        return {"status": value, "sources": {}}
    if isinstance(value, dict):
        return {
            "status": value.get("status") or "",
            "sources": dict(value.get("sources") or {}),
        }
    return {"status": "", "sources": {}}


def record_resolution(pk: int | None, status: str, source: str | None = None) -> None:
    """Record one comic's match-review outcome by source (no-op without a pk)."""
    if pk is None:
        return
    outcomes = get_resolved_outcomes()
    record = _normalize_resolution(outcomes.get(pk))
    if source:
        record["sources"][source] = status
    # Under merge_all_sources one comic can raise a prompt per source, so the
    # file-level status is a reduction: a match from either source is the
    # outcome that matters and outranks the other's skip.
    seen = (*record["sources"].values(), record["status"], status)
    record["status"] = USER_MATCHED if USER_MATCHED in seen else status
    outcomes[pk] = record
    set_resolved_outcomes(outcomes)


def clear_resolved_outcomes() -> None:
    """Drop the whole resolution record (a fresh scan starts clean)."""
    cache.delete(_RESOLVED_KEY)


def overlay_resolutions(
    snapshot: dict[str, Any],
    review_sources_by_pk: dict[int, tuple[str, ...]],
    resolved_outcomes: dict[int, Any],
) -> dict[str, Any]:
    """
    Reconcile a stored snapshot's per-comic statuses with current state.

    A comic still awaiting a prompt wins as ``needs_review`` (the live cache is
    authoritative over the frozen scan); otherwise a recorded resolution
    replaces a stale status with ``user_matched`` / ``user_skipped``. Both land
    in the source column that prompted as well as on the row. The needs-review
    tally is refreshed from the live prompt set. Mutates the passed dict (a
    fresh deserialized copy from the cache) and returns it.
    """
    for comic in snapshot.get("comics") or []:
        pk = comic.get("pk")
        # Snapshots cached before per-source columns have no cells to update.
        cells = comic.setdefault("source_statuses", {})
        if pk in review_sources_by_pk:
            comic["status"] = NEEDS_REVIEW
            for source in review_sources_by_pk[pk]:
                cells[source] = NEEDS_REVIEW
        elif pk in resolved_outcomes:
            record = _normalize_resolution(resolved_outcomes[pk])
            if record["status"]:
                comic["status"] = record["status"]
            cells.update(record["sources"])
    batch = snapshot.get("batch")
    if isinstance(batch, dict):
        batch["needs_review"] = len(review_sources_by_pk)
    return snapshot


# --- resume state ------------------------------------------------------------
#
# To resume a scan the daemon was killed (or paused) mid-way, the web process
# needs the comics not yet processed plus the original scan parameters. The
# capped, frontend-facing snapshot can't carry that (a multi-thousand batch
# would lose queued rows past the cap), so the full, uncapped remainder lives
# in its own key the UI never fetches. An empty remainder clears the key, so
# "resumable" is simply "this key exists with comics in it".


def get_resume_state() -> dict[str, Any] | None:
    """Return the {params, remaining_pks} resume descriptor, or None."""
    return cache.get(_RESUME_KEY) or None


def set_resume_state(params: dict[str, Any], remaining: list[int]) -> None:
    """Persist the resume descriptor, or clear it when nothing remains."""
    if remaining:
        cache.set(
            _RESUME_KEY,
            {"params": params, "remaining_pks": remaining},
            timeout=_NO_TIMEOUT,
        )
    else:
        cache.delete(_RESUME_KEY)


def clear_resume_state() -> None:
    """Drop the resume descriptor (a fresh scan starts clean)."""
    cache.delete(_RESUME_KEY)


def _is_pending(path, pk, stats, review_pks: set) -> bool:
    """
    Whether a comic is still to be processed.

    A comic is done once it lands in a stats bucket (written / no_change /
    errored) or has a pending prompt; everything else (queued + the single
    in-flight) is what Resume re-runs. The one definition behind both
    ``remaining_pks`` and the in-flight election, so the two cannot drift.
    """
    return not (
        path in stats.errored_paths
        or path in stats.written_paths
        or path in stats.no_change_paths
        or pk in review_pks
    )


def remaining_pks(state: SessionState, review_pks: set) -> list[int]:
    """Uncapped pks still to process: not terminal and not awaiting review."""
    stats = state.stats
    return [
        pk
        for path, pk in state.path_to_pk.items()
        if _is_pending(path, pk, stats, review_pks)
    ]


def _elect_in_flight_path(
    state: SessionState, review_pks: set, *, active: bool
) -> Path | None:
    """
    Return the comic being looked up right now, or None when nothing is.

    Read from ``SessionState.live`` — the marker the daemon sets off the
    comicbox event stream and its own stored-id prepass — never guessed from
    ``path_to_pk`` position: ``tag_many`` re-sorts the batch by series
    fingerprint, so position is unrelated to processing order.

    Returning None is a real answer, not a failure. Between comics, before the
    first event, and after a cancel there genuinely is no live lookup, and the
    comic then reads Queued — which is honest, and is exactly what Resume will
    re-run. Guessing a row instead would put a "looking this up right now"
    claim on an arbitrary comic.
    """
    if not active or state.cancelled:
        return None
    path = state.live.path
    if path is None:
        return None
    pk = state.path_to_pk.get(path)
    if pk is None:
        # A live path from a merged batch we never recorded, or a stale
        # marker; nothing to hang the row on.
        return None
    return path if _is_pending(path, pk, state.stats, review_pks) else None


def _comic_status(path, pk, stats, review_pks: set, *, in_flight: bool) -> str:
    """Classify one comic from the scan's accumulated outcome stats."""
    if path in stats.errored_paths:
        return ERROR
    if pk in review_pks:
        return NEEDS_REVIEW
    if path in stats.written_paths:
        return MATCHED
    if path in stats.no_change_paths:
        return NO_MATCH
    return IN_FLIGHT if in_flight else QUEUED


def _row_source_statuses(
    path,
    status: str,
    stats,
    sources: tuple[str, ...],
    waiting_sources: frozenset[str],
    live_source: str,
) -> dict[str, str]:
    """Report what each source did with one comic, as its own column cell."""
    if status == QUEUED:
        # Nothing has touched it yet; the row reads as queued in every column.
        # Kept as an early return rather than falling through: a comic whose
        # first source reported before the scan stopped would otherwise show
        # that verdict beside a Queued row Resume is about to re-run in full.
        return {}
    if status == ERROR:
        # A worker exception is usually archive-level rather than any one
        # source's doing, so every column reports it instead of mis-blaming.
        return dict.fromkeys(sources, ERROR)
    cells = dict(stats.source_status_by_path.get(path, {}))
    if status == IN_FLIGHT:
        # The one live "Looking up" cell, projected from the scan's marker
        # rather than accumulated from events — an event-derived cell is
        # cleared before any publish can sample it.
        if live_source:
            cells[live_source] = IN_FLIGHT
        # A rate-limit wait stalls the comic being looked up right now, and
        # outranks the lookup claim: the source is throttled, not working.
        for source in sources:
            if source in waiting_sources:
                cells[source] = WAITING
    return cells


def _build_comic_rows(
    state: SessionState,
    review_pks: set,
    waiting_sources: frozenset[str],
    *,
    active: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Build per-comic rows in list order plus a status tally."""
    stats = state.stats
    counts: dict[str, int] = dict.fromkeys(
        (QUEUED, IN_FLIGHT, MATCHED, NO_MATCH, NEEDS_REVIEW, ERROR), 0
    )
    rows: list[dict[str, Any]] = []
    in_flight_path = _elect_in_flight_path(state, review_pks, active=active)
    live_source = state.live.source
    for path, pk in state.path_to_pk.items():
        is_live = in_flight_path is not None and path == in_flight_path
        status = _comic_status(path, pk, stats, review_pks, in_flight=is_live)
        counts[status] += 1
        rows.append(
            {
                "pk": pk,
                "path": str(path),
                "status": status,
                "source_statuses": _row_source_statuses(
                    path,
                    status,
                    stats,
                    state.sources,
                    waiting_sources,
                    live_source if is_live else "",
                ),
            }
        )
    return rows, counts


def _order_and_cap(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """In-flight row first, then the rest actionable, queued, finished; capped."""
    # ACTIONABLE is a membership test, not a ranking, so needs-review and
    # error rows sit in front of the live one purely by list position. Past
    # _MAX_COMIC_ROWS of them the live row — the whole point of the table —
    # would be truncated away, so it is hoisted to the head outright.
    actionable = sorted(
        (r for r in rows if r["status"] in ACTIONABLE),
        key=lambda r: r["status"] != IN_FLIGHT,
    )
    queued = [r for r in rows if r["status"] == QUEUED]
    finished = [r for r in rows if r["status"] in FINISHED]
    return (actionable + queued + finished)[:_MAX_COMIC_ROWS]


def _build_sources(
    state: SessionState,
    source_retry_at: dict[str, float],
    waiting_sources: frozenset[str],
) -> list[dict[str, Any]]:
    """One ordered entry per source: rate budget + any live retry countdown."""
    # Live per-account budget (comicbox>=4.3.0 reads it off Metron's
    # X-RateLimit-* headers; earlier versions and cold sessions report {}).
    # The sustained (daily) window is the one worth showing — its limit
    # varies by Metron donor tier; the burst cap is the static
    # rate_per_minute already displayed.
    live = state.session.rate_limit_status() if state.session else {}
    sources = []
    for source in state.sources:
        retry_at = source_retry_at.get(source)
        rate_limited = source in waiting_sources
        sustained = (live.get(source) or {}).get("sustained") or {}
        sources.append(
            {
                "source": source,
                "rate_per_minute": SOURCE_RATE_PER_MINUTE.get(source),
                "rate_limited": rate_limited,
                "retry_at_epoch": retry_at if rate_limited else None,
                "sustained_limit": sustained.get("limit"),
                "sustained_remaining": sustained.get("remaining"),
            }
        )
    return sources


def build_snapshot(
    state: SessionState,
    *,
    session_id: str,
    active: bool,
    eta_epoch: float | None,
    source_retry_at: dict[str, float],
    now_epoch: float,
) -> dict[str, Any]:
    """Fold scan state + pending prompts into a JSON-safe snapshot dict."""
    review_pks = {p.get("pk") for p in get_pending_prompts().values()}
    # One predicate for both the sources strip and the per-comic waiting cells,
    # so a source can never read as limited in one and free in the other.
    waiting_sources = frozenset(
        source
        for source, retry_at in source_retry_at.items()
        if retry_at and retry_at > now_epoch
    )
    rows, counts = _build_comic_rows(state, review_pks, waiting_sources, active=active)
    total = state.total_comics or len(state.path_to_pk)
    batch = {
        "total": total,
        "completed": state.completed_comics,
        "matched": counts[MATCHED],
        "needs_review": counts[NEEDS_REVIEW],
        "no_match": counts[NO_MATCH],
        "error": counts[ERROR],
        "queued": counts[QUEUED] + counts[IN_FLIGHT],
        "sources": list(state.sources),
        "match_mode": state.match_mode,
        "merge_all_sources": state.merge_all_sources,
        "eta_epoch": eta_epoch,
    }
    shown = _order_and_cap(rows)
    return {
        "session_id": session_id,
        "active": active,
        # Has unprocessed comics left → a paused/interrupted session the UI can
        # resume (queued already includes the in-flight one). While ``active``
        # the frontend shows "Tagging" regardless; this matters once inactive.
        "resumable": bool(batch["queued"]),
        "batch": batch,
        "sources": _build_sources(state, source_retry_at, waiting_sources),
        "comics": shown,
        "comic_count": len(rows),
        "shown_count": len(shown),
    }

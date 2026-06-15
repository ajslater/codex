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

- **Per-comic status is derived, not tracked.** ``OnlineTagOutcomeStats``
  already records every comic's path in ``written_paths`` / ``no_change_paths``
  / ``errored_paths`` / ``matched_source_by_path``; "needs review" comes from
  the pending-prompt cache (keyed by pk). The single *in-flight* comic is the
  first not-yet-terminal, not-deferred path in processing order — the scan is
  strictly sequential (one ``tag_many`` loop), so there is never more than one.
- **The comic list is capped** (``_MAX_COMIC_ROWS``) so a batch of thousands
  doesn't bloat the cache or the wire. Actionable rows (in-flight, needs
  review, error) and upcoming (queued) come first; finished rows fill the rest.
  ``comic_count`` always carries the true total so the UI can say "showing N
  of M".
- **Status string values are deliberately snake_case** and pass through the
  camelCase API renderer untouched (it only camelizes dict *keys*); the
  frontend matches on these literals.
- Lives in ``caches["tagging"]`` like the prompts/scan-id state, with no TTL.
  The active flag flips to False when the scan finishes so the final tally
  stays visible until the next batch starts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from codex.cache import tagging_cache as cache
from codex.librarian.onlinetag.estimate import SOURCE_RATE_PER_MINUTE
from codex.librarian.onlinetag.session_cache import get_pending_prompts

if TYPE_CHECKING:
    from codex.librarian.onlinetag.session_state import SessionState

_SNAPSHOT_KEY = "onlinetag:session_snapshot"
_NO_TIMEOUT = None
_MAX_COMIC_ROWS: Final = 500

# Per-comic status values. These are emitted to the frontend verbatim (the
# camelCase renderer rewrites keys, never values), so the frontend matches on
# these exact strings.
QUEUED: Final = "queued"
IN_FLIGHT: Final = "in_flight"
MATCHED: Final = "matched"
NO_MATCH: Final = "no_match"
NEEDS_REVIEW: Final = "needs_review"
ERROR: Final = "error"
# Outcomes of admin match-review actions. A scan never produces these; they are
# overlaid at read time from the resolution record so a comic the admin picked
# or skipped no longer reads as still "needs review".
USER_MATCHED: Final = "user_matched"
USER_SKIPPED: Final = "user_skipped"

# Display ordering buckets: actionable first, then upcoming, then finished.
_ACTIONABLE: Final = (IN_FLIGHT, NEEDS_REVIEW, ERROR)
_FINISHED: Final = (MATCHED, NO_MATCH)

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
    is also exactly what Resume will re-run.
    """
    snapshot = get_snapshot()
    if snapshot and snapshot.get("active"):
        snapshot["active"] = False
        for comic in snapshot.get("comics") or []:
            if comic.get("status") == IN_FLIGHT:
                comic["status"] = QUEUED
        set_snapshot(snapshot)


# --- resolution outcomes -----------------------------------------------------
#
# A scan freezes its snapshot when it finishes, but the admin can keep
# answering deferred prompts afterward — so a comic the snapshot recorded as
# "needs review" may since have been picked or skipped. We record each
# resolution (keyed by comic pk) here and overlay it at read time, which both
# corrects the stale status and surfaces that a human was involved. Cleared
# when a new scan starts; pruned for vanished comics by the janitor.


def get_resolved_outcomes() -> dict[int, str]:
    """Return the {pk: user_matched|user_skipped} resolution record."""
    return cache.get(_RESOLVED_KEY, {}) or {}


def set_resolved_outcomes(outcomes: dict[int, str]) -> None:
    """Replace the resolution record, or clear it when empty."""
    if outcomes:
        cache.set(_RESOLVED_KEY, outcomes, timeout=_NO_TIMEOUT)
    else:
        cache.delete(_RESOLVED_KEY)


def record_resolution(pk: int | None, status: str) -> None:
    """Record one comic's match-review outcome (no-op without a pk)."""
    if pk is None:
        return
    outcomes = get_resolved_outcomes()
    outcomes[pk] = status
    set_resolved_outcomes(outcomes)


def clear_resolved_outcomes() -> None:
    """Drop the whole resolution record (a fresh scan starts clean)."""
    cache.delete(_RESOLVED_KEY)


def overlay_resolutions(
    snapshot: dict[str, Any],
    review_pks: set,
    resolved_outcomes: dict[int, str],
) -> dict[str, Any]:
    """
    Reconcile a stored snapshot's per-comic statuses with current state.

    A comic still awaiting a prompt wins as ``needs_review`` (the live cache is
    authoritative over the frozen scan); otherwise a recorded resolution
    replaces a stale status with ``user_matched`` / ``user_skipped``. The
    needs-review tally is refreshed from the live prompt set. Mutates the
    passed dict (a fresh deserialized copy from the cache) and returns it.
    """
    for comic in snapshot.get("comics") or []:
        pk = comic.get("pk")
        if pk in review_pks:
            comic["status"] = NEEDS_REVIEW
        elif pk in resolved_outcomes:
            comic["status"] = resolved_outcomes[pk]
    batch = snapshot.get("batch")
    if isinstance(batch, dict):
        batch["needs_review"] = len(review_pks)
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


def remaining_pks(state: SessionState, review_pks: set) -> list[int]:
    """
    Uncapped pks still to process: not terminal and not awaiting review.

    Mirrors the buckets ``_comic_status`` reads — a comic is done once it lands
    in a stats bucket (written / no_change / errored) or has a pending prompt;
    everything else (queued + the single in-flight) is what Resume re-runs.
    """
    stats = state.stats
    out: list[int] = []
    for path, pk in state.path_to_pk.items():
        if (
            path in stats.errored_paths
            or path in stats.written_paths
            or path in stats.no_change_paths
            or pk in review_pks
        ):
            continue
        out.append(pk)
    return out


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


def _build_comic_rows(
    state: SessionState, review_pks: set
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Build per-comic rows in processing order plus a status tally."""
    stats = state.stats
    counts: dict[str, int] = dict.fromkeys(
        (QUEUED, IN_FLIGHT, MATCHED, NO_MATCH, NEEDS_REVIEW, ERROR), 0
    )
    rows: list[dict[str, Any]] = []
    in_flight_taken = False
    # path_to_pk preserves insertion order, which is the pk order the scan
    # feeds to tag_many — so the first comic not yet terminal and not deferred
    # is the one currently being looked up.
    for path, pk in state.path_to_pk.items():
        wants_in_flight = state.cancelled is False and not in_flight_taken
        status = _comic_status(path, pk, stats, review_pks, in_flight=wants_in_flight)
        if status == IN_FLIGHT:
            in_flight_taken = True
        counts[status] += 1
        won = stats.matched_source_by_path.get(path) if status == MATCHED else None
        rows.append({"pk": pk, "path": str(path), "status": status, "won_source": won})
    return rows, counts


def _order_and_cap(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Actionable rows first, then queued, then finished; capped, order kept."""
    actionable = [r for r in rows if r["status"] in _ACTIONABLE]
    queued = [r for r in rows if r["status"] == QUEUED]
    finished = [r for r in rows if r["status"] in _FINISHED]
    return (actionable + queued + finished)[:_MAX_COMIC_ROWS]


def _build_sources(
    state: SessionState, source_retry_at: dict[str, float], now_epoch: float
) -> list[dict[str, Any]]:
    """One ordered entry per source: rate budget + any live retry countdown."""
    sources = []
    for source in state.sources:
        retry_at = source_retry_at.get(source)
        rate_limited = bool(retry_at and retry_at > now_epoch)
        sources.append(
            {
                "source": source,
                "rate_per_minute": SOURCE_RATE_PER_MINUTE.get(source),
                "rate_limited": rate_limited,
                "retry_at_epoch": retry_at if rate_limited else None,
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
    rows, counts = _build_comic_rows(state, review_pks)
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
        "sources": _build_sources(state, source_retry_at, now_epoch),
        "comics": shown,
        "comic_count": len(rows),
        "shown_count": len(shown),
    }

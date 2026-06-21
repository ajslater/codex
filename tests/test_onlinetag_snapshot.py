"""
Unit tests for the online-tagging session snapshot builder.

``build_snapshot`` folds a scan's in-memory :class:`SessionState` (its
``OnlineTagOutcomeStats`` plus ``path_to_pk``) and the pending-prompt cache
into the JSON-safe dict the admin Tagging-tab status table renders. The
per-comic status is derived, not tracked: terminal outcomes come from the
stats buckets, "needs review" from the prompt cache (by pk), and the single
in-flight comic is the first not-yet-terminal, not-deferred path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from comicbox.events import AutoWritten, FileError, FileFinished

from codex.librarian.onlinetag import session_snapshot
from codex.librarian.onlinetag.outcome_stats import OnlineTagOutcomeStats
from codex.librarian.onlinetag.session_cache import set_pending_prompts
from codex.librarian.onlinetag.session_snapshot import (
    USER_MATCHED,
    USER_SKIPPED,
    build_snapshot,
    clear_resolved_outcomes,
    clear_resume_state,
    deactivate_snapshot,
    get_resolved_outcomes,
    get_resume_state,
    overlay_resolutions,
    record_resolution,
    remaining_pks,
    set_resume_state,
    set_snapshot,
)
from codex.librarian.onlinetag.session_state import SessionState


@pytest.fixture(autouse=True)
def _clear_prompts():  # pyright: ignore[reportUnusedFunction]
    """Each test starts with an empty pending-prompt + resolution cache."""
    set_pending_prompts({})
    clear_resolved_outcomes()
    clear_resume_state()
    yield
    set_pending_prompts({})
    clear_resolved_outcomes()
    clear_resume_state()


def _state(paths_to_pks, *, sources=("metron", "comicvine")) -> SessionState:
    """Build a SessionState with the given comics in order (session unused)."""
    path_to_pk = {Path(p): pk for p, pk in paths_to_pks}
    return SessionState(
        session=None,  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]
        path_to_pk=path_to_pk,
        match_mode="auto",
        sources=sources,
        total_comics=len(path_to_pk),
    )


def _build(state, **kwargs):
    """Call build_snapshot with sane defaults for the optional knobs."""
    params = {
        "session_id": "sid-1",
        "active": True,
        "eta_epoch": None,
        "source_retry_at": {},
        "now_epoch": 1000.0,
    }
    params.update(kwargs)
    return build_snapshot(state, **params)  # pyright: ignore[reportArgumentType]


def test_first_unprocessed_comic_is_in_flight() -> None:
    """Exactly one queued comic reads as in-flight; the rest stay queued."""
    comics = [("/c/1.cbz", 1), ("/c/2.cbz", 2), ("/c/3.cbz", 3)]
    state = _state(comics)
    snap = _build(state)

    statuses = {row["pk"]: row["status"] for row in snap["comics"]}
    assert statuses == {
        1: session_snapshot.IN_FLIGHT,
        2: session_snapshot.QUEUED,
        3: session_snapshot.QUEUED,
    }
    # In-flight counts toward outstanding queued work.
    assert snap["batch"]["queued"] == len(comics)


def test_terminal_and_review_statuses_derive_from_stats_and_prompts() -> None:
    """Matched / no_match / error come from stats; needs_review from prompts."""
    state = _state(
        [
            ("/c/1.cbz", 1),
            ("/c/2.cbz", 2),
            ("/c/3.cbz", 3),
            ("/c/4.cbz", 4),
            ("/c/5.cbz", 5),
        ]
    )
    stats = OnlineTagOutcomeStats()
    stats.record(AutoWritten(path=Path("/c/1.cbz"), source="metron"))
    stats.record(FileFinished(path=Path("/c/1.cbz"), outcome="written"))
    stats.record(FileFinished(path=Path("/c/2.cbz"), outcome="no_change"))
    stats.record(FileError(path=Path("/c/3.cbz"), error="boom"))
    state.stats = stats
    state.completed_comics = 3
    # Comic 4 is awaiting manual review.
    set_pending_prompts(
        {"fp4": {"pk": 4, "path": "/c/4.cbz", "source": "metron", "candidates": []}}
    )

    snap = _build(state)
    statuses = {row["pk"]: row["status"] for row in snap["comics"]}
    won = {row["pk"]: row["won_sources"] for row in snap["comics"]}

    # Comic 5 is the next unprocessed comic → in-flight.
    assert statuses == {
        1: session_snapshot.MATCHED,
        2: session_snapshot.NO_MATCH,
        3: session_snapshot.ERROR,
        4: session_snapshot.NEEDS_REVIEW,
        5: session_snapshot.IN_FLIGHT,
    }
    assert won[1] == ["metron"]
    # Non-matched rows carry no source attribution.
    assert won[2] == won[5] == []

    batch = snap["batch"]
    assert {k: batch[k] for k in ("matched", "no_match", "error", "needs_review")} == {
        "matched": 1,
        "no_match": 1,
        "error": 1,
        "needs_review": 1,
    }


def test_sources_strip_reports_rate_limit_countdown() -> None:
    """A future per-source retry epoch reports rate_limited with its deadline."""
    cv_retry_epoch = 1030.0
    cv_rate_per_minute = 3
    state = _state([("/c/1.cbz", 1)])
    snap = _build(
        state,
        now_epoch=1000.0,
        source_retry_at={"comicvine": cv_retry_epoch, "metron": 900.0},
    )
    by_source = {s["source"]: s for s in snap["sources"]}

    # comicvine's deadline is in the future → limited with the epoch carried.
    assert by_source["comicvine"]["rate_limited"] is True
    assert by_source["comicvine"]["retry_at_epoch"] == cv_retry_epoch
    assert by_source["comicvine"]["rate_per_minute"] == cv_rate_per_minute
    # metron's deadline already passed → not limited, epoch dropped.
    assert by_source["metron"]["rate_limited"] is False
    assert by_source["metron"]["retry_at_epoch"] is None
    # Order follows the scan's source priority.
    assert [s["source"] for s in snap["sources"]] == ["metron", "comicvine"]


def test_comic_list_is_capped_with_actionable_first() -> None:
    """Over the cap, actionable rows survive and the true total is reported."""
    cap = session_snapshot._MAX_COMIC_ROWS  # noqa: SLF001
    pairs = [(f"/c/{i}.cbz", i) for i in range(cap + 50)]
    state = _state(pairs)
    # Mark everything but the last comic as finished (no_change) so the bulk is
    # non-actionable; the lone unprocessed comic must still be shown.
    stats = OnlineTagOutcomeStats()
    for path, _pk in pairs[:-1]:
        stats.record(FileFinished(path=Path(path), outcome="no_change"))
    state.stats = stats

    snap = _build(state)
    assert snap["comic_count"] == cap + 50
    assert snap["shown_count"] == cap
    assert len(snap["comics"]) == cap
    # The single in-flight comic (last pk) is actionable → kept despite the cap.
    shown_pks = {row["pk"] for row in snap["comics"]}
    assert (cap + 50 - 1) in shown_pks


def test_record_resolution_roundtrip_and_clear() -> None:
    """Resolutions accumulate by pk; a None pk is a no-op; clear empties them."""
    record_resolution(5, USER_SKIPPED)
    record_resolution(6, USER_MATCHED)
    record_resolution(None, USER_MATCHED)  # no comic → ignored
    assert get_resolved_outcomes() == {5: USER_SKIPPED, 6: USER_MATCHED}
    clear_resolved_outcomes()
    assert get_resolved_outcomes() == {}


def test_overlay_replaces_stale_needs_review_with_resolution() -> None:
    """A comic the admin resolved no longer reads as needs_review."""
    state = _state([("/c/1.cbz", 1), ("/c/2.cbz", 2)])
    # Comic 1 was deferred when the snapshot froze.
    set_pending_prompts(
        {"fp1": {"pk": 1, "path": "/c/1.cbz", "source": "metron", "candidates": []}}
    )
    snap = _build(state)
    assert {r["pk"]: r["status"] for r in snap["comics"]}[1] == (
        session_snapshot.NEEDS_REVIEW
    )

    # The admin has since picked a match; the prompt is gone and recorded.
    set_pending_prompts({})
    out = overlay_resolutions(
        snap, review_pks=set(), resolved_outcomes={1: USER_MATCHED}
    )
    statuses = {r["pk"]: r["status"] for r in out["comics"]}
    assert statuses[1] == USER_MATCHED
    assert out["batch"]["needs_review"] == 0


def test_overlay_pending_prompt_wins_over_recorded_resolution() -> None:
    """A still-pending comic stays needs_review even with a recorded outcome."""
    state = _state([("/c/1.cbz", 1)])
    snap = _build(state)
    # A drifted re-queue leaves the comic both recorded and pending again.
    out = overlay_resolutions(snap, review_pks={1}, resolved_outcomes={1: USER_MATCHED})
    assert out["comics"][0]["status"] == session_snapshot.NEEDS_REVIEW
    assert out["batch"]["needs_review"] == 1


def test_snapshot_resumable_reflects_unprocessed_comics() -> None:
    """Resumable is True with queued comics, False once all are terminal."""
    state = _state([("/c/1.cbz", 1), ("/c/2.cbz", 2)])
    assert _build(state)["resumable"] is True

    stats = OnlineTagOutcomeStats()
    stats.record(FileFinished(path=Path("/c/1.cbz"), outcome="no_change"))
    stats.record(FileFinished(path=Path("/c/2.cbz"), outcome="no_change"))
    state.stats = stats
    assert _build(state)["resumable"] is False


def test_deactivate_snapshot_demotes_in_flight_to_queued() -> None:
    """A killed scan's frozen in-flight row reads as queued, not 'Looking up'."""
    state = _state([("/c/1.cbz", 1), ("/c/2.cbz", 2)])
    set_snapshot(_build(state, active=True))

    deactivate_snapshot()

    snap = session_snapshot.get_snapshot()
    assert snap is not None
    assert snap["active"] is False
    statuses = {row["pk"]: row["status"] for row in snap["comics"]}
    # The would-be in-flight comic (pk 1) is demoted; nothing stays in_flight.
    assert session_snapshot.IN_FLIGHT not in statuses.values()
    assert statuses[1] == session_snapshot.QUEUED
    # Still resumable — the demote doesn't change the queued tally.
    assert snap["resumable"] is True


def test_remaining_pks_excludes_terminal_and_review() -> None:
    """remaining_pks returns only queued/in-flight comics, uncapped."""
    state = _state(
        [
            ("/c/1.cbz", 1),
            ("/c/2.cbz", 2),
            ("/c/3.cbz", 3),
            ("/c/4.cbz", 4),
            ("/c/5.cbz", 5),
        ]
    )
    stats = OnlineTagOutcomeStats()
    stats.record(AutoWritten(path=Path("/c/1.cbz"), source="metron"))
    stats.record(FileFinished(path=Path("/c/1.cbz"), outcome="written"))
    stats.record(FileFinished(path=Path("/c/2.cbz"), outcome="no_change"))
    stats.record(FileError(path=Path("/c/3.cbz"), error="boom"))
    state.stats = stats

    # Comic 4 is awaiting review; 5 is still unprocessed.
    assert remaining_pks(state, review_pks={4}) == [5]
    # Without the review, comic 4 is also still to do.
    assert remaining_pks(state, review_pks=set()) == [4, 5]


def test_resume_state_roundtrip_and_empty_clears() -> None:
    """set/get/clear round-trips; an empty remainder clears the key."""
    params = {"sources": ["metron"], "mode": "auto"}
    set_resume_state(params, [7, 8])
    stored = get_resume_state()
    assert stored == {"params": params, "remaining_pks": [7, 8]}

    set_resume_state(params, [])
    assert get_resume_state() is None

    set_resume_state(params, [9])
    clear_resume_state()
    assert get_resume_state() is None

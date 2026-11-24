"""
A run comicbox stops itself must pause, not finish.

Near the end of the day's API budget comicbox stops starting new searches,
and at zero it aborts the lookup — which cancels the session, so every
remaining comic streams back as a cancelled result. Marching through those
would count a whole library as "looked up" in seconds, freeze a
finished-looking snapshot over comics nobody looked at, and clear the resume
descriptor that is the only way to pick them up tomorrow.

So codex treats it as the operator's own Pause: stop at the first cancelled
result, leave the rest queued, stay resumable.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Final

from comicbox.events import (
    SKIP_QUOTA_RESERVED,
    AutoWritten,
    FileFinished,
    NoMatch,
    PromptDeferred,
    Skipped,
    SourceStarted,
)
from loguru import logger

from codex.librarian.onlinetag.outcome_stats import (
    OnlineTagOutcomeStats,
    api_cost_lines,
)
from codex.librarian.onlinetag.session_state import SessionState
from codex.librarian.onlinetag.status import OnlineLookupStatus
from codex.librarian.onlinetag.tag_pass_runner import TagPassRunner
from tests.onlinetag_session_fakes import FakeQueue, double

_QUOTA_REASON: Final = "online: daily API request quota exhausted"


class _QuotaStoppedSession:
    """Comicbox after the daily quota ran out: one result, then cancelled."""

    def __init__(self, paths: list[Path], stop_after: int) -> None:
        self._paths = paths
        self._stop_after = stop_after
        self.abort_reason = _QUOTA_REASON

    def tag_many(self, paths):
        _ = paths
        for index, path in enumerate(self._paths):
            cancelled = index >= self._stop_after
            yield SimpleNamespace(
                path=path,
                tags=None if cancelled else {"series": "S"},
                error=None,
                matched=not cancelled,
                cancelled=cancelled,
            )

    def cancel(self) -> None:
        pass


class _QuotaSkippingSession:
    """
    Comicbox while VerseDB's daily cap is spent and the others carry on.

    VerseDB reports each comic ``Skipped(reason=quota_reserved)``; the run
    itself is not aborted, so no result comes back cancelled.
    """

    abort_reason = None

    def __init__(self, paths: list[Path]) -> None:
        self._paths = paths

    def tag_many(self, paths):
        _ = paths
        for path in self._paths:
            yield SimpleNamespace(
                path=path, tags=None, error=None, matched=False, cancelled=False
            )

    def cancel(self) -> None:
        pass


class TestQuotaPause:
    """The pass stops where comicbox stopped, and says why."""

    def _runner(self) -> TagPassRunner:
        return TagPassRunner(
            double(logger),
            double(FakeQueue()),
            double(SimpleNamespace(update=lambda *_a, **_k: None)),
            lambda _state: None,
            lambda *_a, **_k: None,
        )

    def _pass_over(self, count: int, stop_after: int):
        """Run one pass over ``count`` comics of a series. No DB needed."""
        paths = [Path(f"/c/s{n}.cbz") for n in range(count)]
        state = SessionState(
            session=double(_QuotaStoppedSession(paths, stop_after)),
            path_to_pk={path: n for n, path in enumerate(paths, start=1)},
            sources=("metron",),
        )
        state.total_comics = len(paths)
        status = OnlineLookupStatus()
        status.total = len(paths)
        runner = self._runner()
        runner.lookup_status = status
        runner._run_pass(state, paths, status, {}, flush_writes=False)  # noqa: SLF001
        return state, status

    def test_the_pass_stops_at_the_comic_comicbox_stopped_on(self) -> None:
        state, _status = self._pass_over(4, stop_after=1)

        # Only the comic that really was looked up counts as done.
        assert state.completed_comics == 1
        assert state.cancelled is True

    def test_the_paused_scan_says_why(self) -> None:
        _state, status = self._pass_over(3, stop_after=1)

        assert _QUOTA_REASON in status.subtitle

    def test_a_versedb_quota_skip_does_not_pause_the_scan(self) -> None:
        """One source out of budget is not the run out of budget."""
        paths = [Path(f"/c/v{n}.cbz") for n in range(3)]
        state = SessionState(
            session=double(_QuotaSkippingSession(paths)),
            path_to_pk={path: n for n, path in enumerate(paths, start=1)},
            sources=("metron", "versedb"),
        )
        state.total_comics = len(paths)
        status = OnlineLookupStatus()
        status.total = len(paths)
        runner = self._runner()
        runner.lookup_status = status
        runner._run_pass(state, paths, status, {}, flush_writes=False)  # noqa: SLF001

        assert state.cancelled is False
        assert state.completed_comics == len(paths)

    def test_the_comics_it_never_reached_stay_resumable(self) -> None:
        """``cancelled`` is what keeps the remainder in the resume set."""
        from codex.librarian.onlinetag.session_snapshot import remaining_pks

        state, _status = self._pass_over(4, stop_after=1)

        # Nothing landed in a terminal bucket — the write is enqueued from the
        # batch, not recorded here — so every comic is still to be processed.
        assert set(remaining_pks(state, set())) == set(state.path_to_pk.values())


class TestQuotaReservedOutcome:
    """A comic the quota reserve skipped is not a comic that missed."""

    @staticmethod
    def _skipped_comic(path: Path) -> OnlineTagOutcomeStats:
        stats = OnlineTagOutcomeStats()
        stats.record(Skipped(path=path, source="metron", reason=SKIP_QUOTA_RESERVED))
        stats.record(FileFinished(path=path, outcome="no_change"))
        return stats

    def test_a_quota_skipped_comic_is_not_recorded_as_a_miss(self) -> None:
        path = Path("/c/a.cbz")

        stats = self._skipped_comic(path)

        assert path in stats.quota_reserved_paths
        assert path not in stats.no_change_paths
        assert stats.skipped == 0

    def test_the_source_claims_nothing_about_a_comic_it_never_searched(self) -> None:
        """An empty cell is honest; "No match" would not be."""
        path = Path("/c/a.cbz")

        stats = self._skipped_comic(path)

        assert stats.source_status_by_path.get(path, {}).get("metron") is None

    def test_an_ordinary_skip_still_counts_as_a_miss(self) -> None:
        """Only the quota reason is special; a declined match is a real one."""
        path = Path("/c/a.cbz")
        stats = OnlineTagOutcomeStats()

        stats.record(Skipped(path=path, source="metron", reason="matcher_declined"))
        stats.record(FileFinished(path=path, outcome="no_change"))

        assert stats.quota_reserved_paths == set()
        assert path in stats.no_change_paths

    def test_a_comic_every_other_source_missed_stays_resumable(self) -> None:
        """VerseDB never looked, so the miss is not final."""
        from codex.librarian.onlinetag.session_snapshot import remaining_pks

        path = Path("/c/a.cbz")
        state = SessionState(
            session=None,  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]
            path_to_pk={path: 1},
            sources=("metron", "versedb"),
        )
        for event in (
            SourceStarted(path=path, source="metron"),
            NoMatch(path=path, source="metron"),
            Skipped(path=path, source="versedb", reason=SKIP_QUOTA_RESERVED),
            FileFinished(path=path, outcome="no_change"),
        ):
            state.stats.record(event)

        assert remaining_pks(state, set()) == [1]
        assert state.stats.left_for_next_run == 1
        assert state.stats.source_status_by_path[path] == {"metron": "no_match"}

    def test_a_comic_another_source_wrote_is_counted_once(self) -> None:
        """Matched, not also left for the next run."""
        path = Path("/c/a.cbz")
        stats = OnlineTagOutcomeStats()
        for event in (
            Skipped(path=path, source="versedb", reason=SKIP_QUOTA_RESERVED),
            AutoWritten(path=path, source="metron"),
            FileFinished(path=path, outcome="written"),
        ):
            stats.record(event)

        assert stats.matched == 1
        assert stats.left_for_next_run == 0
        summary = stats.summary(elapsed="2 seconds")
        assert "1 comic — matched 1 (metron 1)" in summary
        assert "left for the next run" not in summary

    def test_a_comic_another_source_deferred_is_deferred_once(self) -> None:
        """It waits on its prompt, not on the next run."""
        path = Path("/c/a.cbz")
        stats = OnlineTagOutcomeStats()
        for event in (
            Skipped(path=path, source="versedb", reason=SKIP_QUOTA_RESERVED),
            PromptDeferred(path=path, source="metron"),
            FileFinished(path=path, outcome="no_change"),
        ):
            stats.record(event)

        assert stats.deferred == 1
        assert stats.left_for_next_run == 0
        assert "left for the next run" not in stats.summary(elapsed="2 seconds")

    def test_the_summary_says_what_is_left_for_next_time(self) -> None:
        stats = self._skipped_comic(Path("/c/a.cbz"))

        summary = stats.summary(elapsed="2 seconds")

        assert "1 left for the next run (daily API quota)" in summary


class TestApiCostLines:
    """The end-of-session cost report, from comicbox's own send counters."""

    @staticmethod
    def _counts(**overrides) -> SimpleNamespace:
        """Stand in for comicbox's per-source HTTP counters."""
        fields = {
            "requests": {"issues_list": 12, "issue": 7},
            "rejections": 0,
            "blocked_seconds": 0.0,
            "burst_limit": 20,
            "burst_remaining": 18,
            "sustained_limit": 5000,
            "sustained_remaining": 4321,
        }
        fields.update(overrides)
        return SimpleNamespace(**fields)

    def test_it_reports_the_total_its_breakdown_and_the_budget(self) -> None:
        lines = api_cost_lines({"metron": self._counts()})

        assert len(lines) == 1
        assert "metron API: 19 requests" in lines[0]
        assert "7 issue, 12 issues_list" in lines[0]
        assert "18/20 this minute, 4321/5000 today left" in lines[0]

    def test_it_reports_rejections_and_time_spent_pacing(self) -> None:
        lines = api_cost_lines(
            {"metron": self._counts(rejections=3, blocked_seconds=42.4)}
        )

        assert "3 rate-limited" in lines[0]
        assert "42s paced" in lines[0]

    def test_a_source_that_sent_nothing_gets_no_line(self) -> None:
        lines = api_cost_lines({"comicvine": self._counts(requests={}, rejections=0)})

        assert lines == []


class TestPauseReasonInTheSnapshot:
    """The frozen snapshot explains a pause the operator did not ask for."""

    def test_the_snapshot_carries_the_reason(self) -> None:
        from codex.librarian.onlinetag.session_snapshot import build_snapshot

        state = SessionState(session=double(None), sources=("metron",))
        state.pause_reason = _QUOTA_REASON

        snapshot = build_snapshot(
            state,
            session_id="sid",
            active=False,
            eta_epoch=None,
            source_retry_at={},
            now_epoch=0.0,
        )

        assert snapshot["pause_reason"] == _QUOTA_REASON

    def test_an_ordinary_finish_explains_nothing(self) -> None:
        """An empty reason is what tells the table to stay quiet."""
        from codex.librarian.onlinetag.session_snapshot import build_snapshot

        state = SessionState(session=double(None), sources=("metron",))

        snapshot = build_snapshot(
            state,
            session_id="sid",
            active=False,
            eta_epoch=None,
            source_retry_at={},
            now_epoch=0.0,
        )

        assert snapshot["pause_reason"] == ""

"""
Unit tests for the online-tagging end-of-session outcome summary.

:class:`OnlineTagOutcomeStats` folds the comicbox event stream into
per-comic tallies. ``FileFinished`` is the per-comic anchor; ``AutoWritten``
attributes a match to its source; ``PromptDeferred`` and ``FileError`` mark
comics queued for manual matching and comics that raised.

The same fold also builds ``source_status_by_path`` — what each source did
with each comic — which the snapshot renders as one status column per source.
"""

from __future__ import annotations

from pathlib import Path

from comicbox.events import (
    AutoWritten,
    FileError,
    FileFinished,
    FileParsed,
    NoMatch,
    PromptDeferred,
    SearchStarted,
    Skipped,
)

from codex.librarian.onlinetag import statuses
from codex.librarian.onlinetag.outcome_stats import OnlineTagOutcomeStats


def _matched(stats: OnlineTagOutcomeStats, path: Path, source: str) -> None:
    """Record a comic auto-matched and written by ``source``."""
    stats.record(AutoWritten(path=path, source=source))
    stats.record(FileFinished(path=path, outcome="written"))


def test_empty_session_has_no_activity() -> None:
    """A session with no events reports zero across every bucket."""
    stats = OnlineTagOutcomeStats()
    assert stats.total == 0
    assert stats.matched == 0
    assert stats.skipped == 0
    assert stats.deferred == 0


def test_counts_matches_skips_prompts_and_errors() -> None:
    """Every outcome bucket tallies and renders into the summary line."""
    stats = OnlineTagOutcomeStats()
    _matched(stats, Path("/c/1.cbz"), "metron")
    _matched(stats, Path("/c/2.cbz"), "metron")
    _matched(stats, Path("/c/3.cbz"), "comicvine")
    # An ambiguous comic deferred for a manual prompt (no match written).
    stats.record(PromptDeferred(path=Path("/c/4.cbz"), source="metron"))
    stats.record(FileFinished(path=Path("/c/4.cbz"), outcome="no_change"))
    # A comic nothing matched and nothing deferred.
    stats.record(FileFinished(path=Path("/c/5.cbz"), outcome="no_change"))
    # A comic that raised before finishing.
    stats.record(FileError(path=Path("/c/6.cbz"), error="boom"))

    snapshot = (
        stats.matched,
        stats.skipped,
        stats.deferred,
        stats.errored,
        stats.total,
    )
    assert snapshot == (3, 1, 1, 1, 6)

    summary = stats.summary(elapsed="5 seconds")
    assert summary == (
        "Online tag session finished in 5 seconds: 6 comics — "
        "matched 3 (comicvine 1, metron 2), 1 skipped, "
        "1 deferred for manual prompts, 1 errored."
    )


def test_match_without_autowritten_is_reported_as_refreshed() -> None:
    """A win with no AutoWritten event falls into the refreshed bucket."""
    # A stored-id refresh wins (FileFinished written) without an AutoWritten
    # event, so it can't be attributed to a source by name.
    stats = OnlineTagOutcomeStats()
    stats.record(FileFinished(path=Path("/c/1.cbz"), outcome="written"))
    _matched(stats, Path("/c/2.cbz"), "metron")

    # "matched 2" in the summary line proves the count without a magic compare.
    summary = stats.summary(elapsed="2 seconds")
    assert "matched 2 (metron 1, 1 refreshed from stored id)" in summary


def test_merge_all_sources_accumulates_every_winning_source() -> None:
    """Under merge a comic auto-written by both sources keeps both, deduped."""
    stats = OnlineTagOutcomeStats()
    path = Path("/c/1.cbz")
    stats.record(AutoWritten(path=path, source="metron"))
    stats.record(AutoWritten(path=path, source="comicvine"))
    # A duplicate event for the same source must not double-list it.
    stats.record(AutoWritten(path=path, source="metron"))
    stats.record(FileFinished(path=path, outcome="written"))

    assert stats.matched_source_by_path[path] == ["metron", "comicvine"]
    # Both sources show in the breakdown; nothing falls to the refreshed bucket.
    summary = stats.summary(elapsed="1 second")
    assert "matched 1 (comicvine 1, metron 1)" in summary
    assert "refreshed from stored id" not in summary


def test_matched_comic_with_incidental_deferred_prompt_counts_as_matched() -> None:
    """A matched comic with an incidental other-source deferral is matched."""
    # A comic won by comicvine that also deferred a metron prompt is matched,
    # not deferred — the deferral only counts when the comic went unmatched.
    stats = OnlineTagOutcomeStats()
    path = Path("/c/1.cbz")
    stats.record(PromptDeferred(path=path, source="metron"))
    _matched(stats, path, "comicvine")

    assert stats.matched == 1
    assert stats.deferred == 0
    assert stats.skipped == 0


def test_unrelated_events_are_ignored() -> None:
    """Events outside the tracked set move no tally."""
    stats = OnlineTagOutcomeStats()
    stats.record(FileParsed(path=Path("/c/1.cbz")))
    assert stats.total == 0


def test_singular_comic_phrasing() -> None:
    """A one-comic session uses the singular noun."""
    stats = OnlineTagOutcomeStats()
    _matched(stats, Path("/c/1.cbz"), "metron")
    assert "1 comic — " in stats.summary(elapsed="1 second")


def test_source_status_records_outcomes_only_never_liveness() -> None:
    """Starting a search records nothing; only what a source *did* lands here."""
    stats = OnlineTagOutcomeStats()
    path = Path("/c/1.cbz")

    # Work in progress is not an outcome. It lives on SessionState.live and is
    # projected into the snapshot, because an event-derived cell is cleared
    # before any publish can sample it.
    stats.record(SearchStarted(path=path, source="metron"))
    assert path not in stats.source_status_by_path

    stats.record(AutoWritten(path=path, source="metron"))
    stats.record(SearchStarted(path=path, source="comicvine"))
    assert stats.source_status_by_path[path] == {"metron": statuses.MATCHED}


def test_source_status_records_no_match_declined_and_deferred() -> None:
    """No-match and a declined match both read as no_match; a prompt as review."""
    stats = OnlineTagOutcomeStats()
    no_match_path = Path("/c/1.cbz")
    declined_path = Path("/c/2.cbz")
    review_path = Path("/c/3.cbz")

    stats.record(NoMatch(path=no_match_path, source="metron"))
    stats.record(
        Skipped(path=declined_path, source="metron", reason="matcher_declined")
    )
    stats.record(PromptDeferred(path=review_path, source="comicvine"))

    assert stats.source_status_by_path[no_match_path] == {"metron": statuses.NO_MATCH}
    assert stats.source_status_by_path[declined_path] == {"metron": statuses.NO_MATCH}
    assert stats.source_status_by_path[review_path] == {
        "comicvine": statuses.NEEDS_REVIEW
    }


def test_a_search_that_never_reported_leaves_no_cell() -> None:
    """A source whose search raised emits nothing, so it contributes no cell."""
    stats = OnlineTagOutcomeStats()
    path = Path("/c/1.cbz")
    stats.record(AutoWritten(path=path, source="metron"))
    # comicvine's search raised: comicbox logs it and emits nothing.
    stats.record(SearchStarted(path=path, source="comicvine"))
    stats.record(FileFinished(path=path, outcome="written"))

    # No clean-up pass needed — the phantom was never recorded.
    assert stats.source_status_by_path[path] == {"metron": statuses.MATCHED}


def test_erroring_a_comic_leaves_no_live_cell_behind() -> None:
    """A comic that raised mid-search never recorded a lookup to strand."""
    stats = OnlineTagOutcomeStats()
    path = Path("/c/1.cbz")
    stats.record(SearchStarted(path=path, source="metron"))
    stats.record(FileError(path=path, error="boom"))

    assert path not in stats.source_status_by_path
    assert path in stats.errored_paths


def test_record_prefetch_match_seeds_every_structure() -> None:
    """A stored-id win emits no events, so the prepass seeds them by hand."""
    stats = OnlineTagOutcomeStats()
    path = Path("/c/1.cbz")

    stats.record_prefetch_match(path, "metron")
    # A second call for the same source must not double-list it.
    stats.record_prefetch_match(path, "metron")

    assert stats.written_paths == {path}
    assert stats.matched_source_by_path[path] == ["metron"]
    assert stats.source_status_by_path[path] == {"metron": statuses.MATCHED}
    assert stats.matched == 1

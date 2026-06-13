"""
Unit tests for the online tagging time estimate.

Mirrors the launcher dialog's algorithm: total calls (comics x calls-per-mode)
over the slowest enabled source's per-minute rate.
"""

from __future__ import annotations

from typing import Final

from codex.librarian.onlinetag.estimate import estimate_seconds

_AUTO_METRON_SECONDS: Final = 90.0
_SLOWEST_SOURCE_SECONDS: Final = 600.0
_CAREFUL_SECONDS: Final = 150.0
_EAGER_SECONDS: Final = 60.0
_UNKNOWN_DEFAULTS_SECONDS: Final = 180.0
_MERGE_TWO_SOURCES_SECONDS: Final = 1200.0


def test_zero_remaining_is_zero() -> None:
    """No remaining comics means no time."""
    assert estimate_seconds(0, "auto", ("metron",)) == 0.0


def test_no_sources_is_zero() -> None:
    """No enabled sources means no time."""
    assert estimate_seconds(10, "auto", ()) == 0.0


def test_auto_mode_metron() -> None:
    """10 comics x 3 calls / 20 per-minute = 1.5 min = 90s."""
    assert estimate_seconds(10, "auto", ("metron",)) == _AUTO_METRON_SECONDS


def test_slowest_source_binds() -> None:
    """
    Comicvine (3/min) is slower than metron (20/min) and binds the rate.

    10 x 3 / 3 = 10 min = 600s.
    """
    assert (
        estimate_seconds(10, "auto", ("metron", "comicvine")) == _SLOWEST_SOURCE_SECONDS
    )


def test_match_mode_scales_calls() -> None:
    """Careful (5 calls/comic) and eager (2 calls/comic) scale total calls."""
    careful = estimate_seconds(10, "careful", ("metron",))
    eager = estimate_seconds(10, "eager", ("metron",))
    assert careful == _CAREFUL_SECONDS
    assert eager == _EAGER_SECONDS


def test_unknown_mode_and_source_use_defaults() -> None:
    """
    Unknown mode -> 3 calls/comic; unknown source -> 10/min default.

    10 x 3 / 10 = 3 min = 180s.
    """
    assert estimate_seconds(10, "bogus", ("unknown",)) == _UNKNOWN_DEFAULTS_SECONDS


def test_merge_all_sources_multiplies_calls() -> None:
    """
    Merge mode queries every source per comic, so calls scale with source count.

    10 x 3 x 2 sources / 3 per-minute (slowest) = 20 min = 1200s, double the
    first-match-wins estimate.
    """
    assert (
        estimate_seconds(10, "auto", ("metron", "comicvine"), merge_all_sources=True)
        == _MERGE_TWO_SOURCES_SECONDS
    )


def test_merge_all_sources_single_source_is_noop() -> None:
    """With one source there's nothing to merge, so the estimate is unchanged."""
    assert (
        estimate_seconds(10, "auto", ("metron",), merge_all_sources=True)
        == _AUTO_METRON_SECONDS
    )

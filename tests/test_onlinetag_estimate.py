"""
The codex estimate seam delegates to comicbox.online_estimate.

The request/rate model and its full test matrix live in comicbox (4.1.0); these
just guard that codex's thin adapter forwards correctly and re-exports the rate
map the session snapshot reads.
"""

from __future__ import annotations

from typing import Final

from codex.librarian.onlinetag.estimate import SOURCE_RATE_PER_MINUTE, estimate_seconds

_METRON_SECONDS: Final = 60.0
_METRON_RATE: Final = 20
_COMICVINE_RATE: Final = 3


def test_estimate_seconds_delegates_to_comicbox() -> None:
    """Metron's flat two-step: 10 comics x 2 requests / 20 per-minute = 60s."""
    assert estimate_seconds(10, ("metron",)) == _METRON_SECONDS


def test_estimate_seconds_passes_merge_flag() -> None:
    """
    merge_all_sources reaches comicbox and changes the estimate.

    Merge queries every source per comic (summing their paces); first-match-
    wins stops at the costliest single source. So the same run costs strictly
    more merged. Assert that forwarding effect rather than comicbox's exact
    arithmetic, which is comicbox's own test matrix (and rate model) to own.
    """
    sources = ("metron", "comicvine")
    merged = estimate_seconds(10, sources, merge_all_sources=True)
    first_wins = estimate_seconds(10, sources)
    assert merged > first_wins


def test_effort_is_the_axis_that_moves_the_estimate() -> None:
    """
    More effort buys more Comic Vine calls, so it costs more time.

    Match mode used to key this and never belonged: it decides how a
    verdict is applied once the calls are already spent.
    """
    minimal = estimate_seconds(10, ("comicvine",), effort="minimal")
    balanced = estimate_seconds(10, ("comicvine",), effort="balanced")
    thorough = estimate_seconds(10, ("comicvine",), effort="thorough")
    assert minimal < balanced < thorough


def test_metron_ignores_effort() -> None:
    """Metron answers in one call and has no fan-out to bound."""
    for effort in ("minimal", "balanced", "thorough"):
        assert estimate_seconds(10, ("metron",), effort=effort) == _METRON_SECONDS


def test_source_rate_per_minute_reexported() -> None:
    """The snapshot reads the per-source rate map through this seam."""
    assert SOURCE_RATE_PER_MINUTE["metron"] == _METRON_RATE
    assert SOURCE_RATE_PER_MINUTE["comicvine"] == _COMICVINE_RATE

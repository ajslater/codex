"""
Estimate how long an online tagging run will take.

This mirrors the "tag online" launcher dialog's estimate
(frontend/src/components/online-tag/launcher-dialog.vue) so the number the
admin saw before starting carries forward into the live "Look Up Online
Tags" status countdown. Keep the constants and the math in sync with that
component — the whole point is that the two agree.

The model is deliberately simple: a run's wall-clock is bound by the
slowest enabled source's per-minute throughput (first-match-wins means a
comic isn't done until the binding source answers), times the number of API
calls each comic needs (a function of match mode), over the comics left.

When merging all sources (comicbox first_wins=False) every enabled source is
queried for every comic instead of stopping at the first match, so the call
count is multiplied by the number of sources — a conservative over-estimate
consistent with the slowest-source bottleneck above.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

# Per-minute request budgets per source. Matches launcher-dialog SOURCE_RATES.
_SOURCE_RATE_PER_MINUTE: Final = MappingProxyType({"metron": 20, "comicvine": 3})

# API calls per comic by match mode. Matches MATCH_MODE_CALLS_PER_COMIC.
_MATCH_MODE_CALLS: Final = MappingProxyType({"eager": 2, "auto": 3, "careful": 5})

# Fallbacks for unknown mode / no recognized source, mirroring the dialog.
_DEFAULT_CALLS_PER_COMIC: Final = 3
_DEFAULT_RATE_PER_MINUTE: Final = 10


def _calls_per_comic(mode: str) -> int:
    return _MATCH_MODE_CALLS.get(mode, _DEFAULT_CALLS_PER_COMIC)


def _slowest_rate_per_minute(sources: tuple[str, ...]) -> int:
    rates = [
        _SOURCE_RATE_PER_MINUTE[s] for s in sources if s in _SOURCE_RATE_PER_MINUTE
    ]
    return min(rates) if rates else _DEFAULT_RATE_PER_MINUTE


def estimate_seconds(
    remaining_comics: int,
    mode: str,
    sources: tuple[str, ...],
    *,
    merge_all_sources: bool = False,
) -> float:
    """Estimated seconds to look up ``remaining_comics`` more comics."""
    if remaining_comics <= 0 or not sources:
        return 0.0
    # Merge mode queries every source per comic instead of the first match.
    source_multiplier = len(sources) if merge_all_sources else 1
    total_calls = remaining_comics * _calls_per_comic(mode) * source_multiplier
    minutes = total_calls / _slowest_rate_per_minute(sources)
    return minutes * 60.0

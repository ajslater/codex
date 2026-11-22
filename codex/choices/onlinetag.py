"""
Online-tag run estimate model, derived from comicbox.

The launcher dialog (``frontend/src/components/online-tag/launcher-dialog.vue``)
estimates a run's time and request count client-side. The per-source rates and
the per-comic request model come from comicbox (``comicbox.online_estimate``)
so the JS estimate tracks the backend instead of hand-syncing constants.
Emitted to ``frontend/src/choices/tagging-estimate.json`` by
``choices_to_json.py``. Display labels stay in the component — they're UI copy.
"""

from types import MappingProxyType
from typing import Final

from comicbox.config.online import Effort
from comicbox.formats.base.online.rate_limits import COMICVINE_DEFAULT_PER_HOUR
from comicbox.online_estimate import (
    DEFAULT_REQUESTS_PER_COMIC,
    SOURCE_RATE_PER_MINUTE,
    requests_per_comic,
)

from codex.librarian.onlinetag.sources import SUPPORTED_SOURCES

# Hourly ceilings a source documents outright: Comic Vine's 200/hour cap.
# Any other source's effective ceiling is its per-minute cap projected over
# the hour.
_DOCUMENTED_PER_HOUR: Final = MappingProxyType(
    {"comicvine": COMICVINE_DEFAULT_PER_HOUR}
)


def _source_rate(source: str) -> MappingProxyType:
    """Return one source's rates for the launcher's rate-limit warning."""
    per_minute = SOURCE_RATE_PER_MINUTE[source]
    per_hour = _DOCUMENTED_PER_HOUR.get(source, per_minute * 60)
    return MappingProxyType({"per_minute": per_minute, "per_hour": per_hour})


# Effective per-source rate limits for the launcher's rate-limit warning.
# ``per_minute`` is comicbox's estimate rate; ``per_hour`` is the effective
# hourly ceiling.
_SOURCE_RATES: Final = MappingProxyType(
    {source: _source_rate(source) for source in SUPPORTED_SOURCES}
)

# What one comic costs against each source, by effort, priced by comicbox.
# Only a source that fans out per candidate (Comic Vine) varies: a discovery
# pair, then a list of issues whose length is what effort buys, then the
# fetch that accepts a match. Match mode does not appear because it changes
# no request count -- it decides how a verdict is applied, after the calls
# are already spent.
_REQUESTS_PER_COMIC: Final = MappingProxyType(
    {
        source: MappingProxyType(
            {
                effort.value: requests_per_comic(source, effort.value)
                for effort in Effort
            }
        )
        for source in SUPPORTED_SOURCES
    }
)

TAGGING_ESTIMATE: Final = MappingProxyType(
    {
        "source_rates": _SOURCE_RATES,
        "requests_per_comic": _REQUESTS_PER_COMIC,
        "default_requests_per_comic": DEFAULT_REQUESTS_PER_COMIC,
    }
)

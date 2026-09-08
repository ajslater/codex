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

from comicbox.formats.base.online.rate_limits import COMICVINE_DEFAULT_PER_HOUR
from comicbox.online_estimate import (
    COMICVINE_DISCOVERY_REQUESTS,
    COMICVINE_FETCH_REQUESTS,
    COMICVINE_ISSUE_LIST_REQUESTS_BY_EFFORT,
    DEFAULT_REQUESTS_PER_COMIC,
    METRON_REQUESTS_PER_COMIC,
    SOURCE_RATE_PER_MINUTE,
)

# Effective per-source rate limits for the launcher's rate-limit warning.
# ``per_minute`` is comicbox's estimate rate; ``per_hour`` is the effective
# hourly ceiling — Metron's per-minute cap projected over the hour, Comic Vine's
# documented 200/hour cap.
_SOURCE_RATES = MappingProxyType(
    {
        "metron": MappingProxyType(
            {
                "per_minute": SOURCE_RATE_PER_MINUTE["metron"],
                "per_hour": SOURCE_RATE_PER_MINUTE["metron"] * 60,
            }
        ),
        "comicvine": MappingProxyType(
            {
                "per_minute": SOURCE_RATE_PER_MINUTE["comicvine"],
                "per_hour": COMICVINE_DEFAULT_PER_HOUR,
            }
        ),
    }
)

# What one comic costs against Comic Vine, by effort. Comic Vine is the
# only source that fans out per candidate, so it is the only one whose
# cost varies: a discovery pair, then a list of issues whose length is
# what effort buys, then the fetch that accepts a match. Match mode does
# not appear because it changes no request count -- it decides how a
# verdict is applied, after the calls are already spent.
_COMICVINE_REQUESTS_BY_EFFORT = MappingProxyType(
    {
        effort: COMICVINE_DISCOVERY_REQUESTS + issue_list + COMICVINE_FETCH_REQUESTS
        for effort, issue_list in COMICVINE_ISSUE_LIST_REQUESTS_BY_EFFORT.items()
    }
)

TAGGING_ESTIMATE = MappingProxyType(
    {
        "source_rates": _SOURCE_RATES,
        "metron_requests_per_comic": METRON_REQUESTS_PER_COMIC,
        "comicvine_requests_by_effort": _COMICVINE_REQUESTS_BY_EFFORT,
        "default_requests_per_comic": DEFAULT_REQUESTS_PER_COMIC,
    }
)

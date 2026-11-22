"""
Online-tag run estimate model and source credits, derived from comicbox.

The launcher dialog (``frontend/src/components/online-tag/launcher-dialog.vue``)
estimates a run's time and request count client-side. The per-source rates and
the per-comic request model come from comicbox (``comicbox.online_estimate``)
so the JS estimate tracks the backend instead of hand-syncing constants.
Emitted to ``frontend/src/choices/tagging-estimate.json`` by
``choices_to_json.py``. Display labels stay in the component — they're UI copy.

``SOURCE_ATTRIBUTION`` is the credit a source's terms require wherever its data
is shown, emitted to ``tagging-attribution.json``. It is comicbox's own text and
link, not a copy: the review dialog, the Tagging tab and the metadata pane all
read it from there.
"""

from types import MappingProxyType
from typing import Final

from comicbox.config.online import Effort
from comicbox.formats.base.online.rate_limits import (
    COMICVINE_DEFAULT_PER_HOUR,
    VERSEDB_DEFAULT_PER_DAY,
    VERSEDB_DEFAULT_PER_HOUR,
)
from comicbox.online_estimate import (
    DEFAULT_REQUESTS_PER_COMIC,
    SOURCE_RATE_PER_MINUTE,
    requests_per_comic,
)
from comicbox.online_session import source_attribution

from codex.librarian.onlinetag.sources import SUPPORTED_SOURCES

# Hourly ceilings a source documents outright: Comic Vine's 200/hour per
# endpoint, VerseDB's free tier's 300/hour. Any other source's effective
# ceiling is its per-minute cap projected over the hour.
_DOCUMENTED_PER_HOUR: Final = MappingProxyType(
    {"comicvine": COMICVINE_DEFAULT_PER_HOUR, "versedb": VERSEDB_DEFAULT_PER_HOUR}
)
# Daily ceilings that bind whoever the account is. Metron's varies by donor
# tier, so it is left out rather than guessed.
_DOCUMENTED_PER_DAY: Final = MappingProxyType({"versedb": VERSEDB_DEFAULT_PER_DAY})


def _source_rate(source: str) -> MappingProxyType:
    """Return one source's rates for the launcher's rate-limit warning."""
    per_minute = SOURCE_RATE_PER_MINUTE[source]
    return MappingProxyType(
        {
            "per_minute": per_minute,
            "per_hour": _DOCUMENTED_PER_HOUR.get(source, per_minute * 60),
            "per_day": _DOCUMENTED_PER_DAY.get(source),
        }
    )


# Effective per-source rate limits for the launcher's rate-limit warning.
# ``per_minute`` is comicbox's estimate rate; ``per_hour`` is the effective
# hourly ceiling; ``per_day`` is a documented daily cap, or None.
_SOURCE_RATES: Final = MappingProxyType(
    {source: _source_rate(source) for source in SUPPORTED_SOURCES}
)

# What one comic costs against each source, by effort, priced by comicbox.
# Only a source that fans out per candidate (Comic Vine) varies; Metron and
# VerseDB cost the same whatever effort asks for. Comic Vine spends a discovery
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

# The credit each supported source's terms require, as comicbox words it and
# links it. Only sources that ask for one appear.
SOURCE_ATTRIBUTION: Final = MappingProxyType(
    {
        source: MappingProxyType({"text": credit.text, "url": credit.url})
        for source in SUPPORTED_SOURCES
        if (credit := source_attribution(source)) is not None
    }
)

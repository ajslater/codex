"""
Series attributes a tag write saves to the database.

An online match brings the series' years, status and summary, but no
format codex writes holds the end year, the status or the summary, and
ComicInfo has no start year either. The re-read that follows a write
only sees the file, so on their own these values would be lost.

The tag writer hands them to that re-read instead, and the importer lays
them over the series the file names. That puts them on the row the comic
lands on, which is a different row whenever the write names a new
publisher or series. The importer's batch rules settle comics of one
series that disagree: the earliest start year, the latest end year and
the first comic's status and summary. A later write's values replace a
stored row's. Empty values are left out, so a write never clears one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from comicbox.enums.comicbox import SeriesStatusEnum
from comicbox.formats.comicbox.schema import SERIES_KEY

from codex.librarian.scribe.importer.const import (
    END_YEAR_FIELD_NAME,
    START_YEAR_FIELD_NAME,
    STATUS_FIELD_NAME,
    SUMMARY_FIELD_NAME,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

_SERIES_ATTR_KEYS: Final = (
    START_YEAR_FIELD_NAME,
    END_YEAR_FIELD_NAME,
    STATUS_FIELD_NAME,
    SUMMARY_FIELD_NAME,
)


def _status_value(status: Any) -> str | None:
    """Return a status as ``SeriesStatusChoices`` stores it, or None."""
    try:
        return SeriesStatusEnum(status).value
    except ValueError:
        return None


def patch_series_attrs(patch: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the non-empty series attributes a tag write patch carries."""
    series = (patch or {}).get(SERIES_KEY) or {}
    attrs = {key: series.get(key) for key in _SERIES_ATTR_KEYS}
    if attrs[STATUS_FIELD_NAME] is not None:
        attrs[STATUS_FIELD_NAME] = _status_value(attrs[STATUS_FIELD_NAME])
    return {key: value for key, value in attrs.items() if value not in (None, "")}

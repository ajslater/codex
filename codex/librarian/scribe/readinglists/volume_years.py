"""
Learn the start year of each volume of a multi-volume series, once.

Migration 0062 gives a series' only volume its start year, but the volumes
of a series that has several keep none until their comics are read again,
and a library that does not change is never read again. The year is the
volume's, so one comic of each is enough. The migration leaves a mark and
the librarian queues the re-read and a rematch once, at its next start.

A dump made before the migration brings the folded years back when it is
restored, so a restore unfolds its references by the same rules.
"""

from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from django.db.models import Count, Min

from codex.librarian.scribe.readinglists.tasks import ReadingListRematchTask
from codex.librarian.scribe.tasks import ForceUpdateComicsTask
from codex.models import Comic, Series, Timestamp, Volume

_KEY = Timestamp.Choices.VOLUME_START_YEARS.value
_PENDING = "pending"


def volume_year_comics() -> frozenset[int]:
    """Return the lowest live comic of each yearless volume of a folded series."""
    multi_volume = (
        Volume.objects.values("series_id")
        .annotate(volumes=Count("pk"))
        .filter(volumes__gt=1)
        .values("series_id")
    )
    return frozenset(
        Comic.objects.filter(
            series_id__in=multi_volume,
            series__start_year__isnull=False,
            volume__start_year__isnull=True,
            missing_since__isnull=True,
        )
        .values("volume_id")
        .annotate(first=Min("pk"))
        .values_list("first", flat=True)
    )


def queue_volume_start_years(queue) -> None:
    """Queue the re-read and a full rematch if migration 0062 asked for them."""
    if not Timestamp.objects.filter(key=_KEY, value=_PENDING).exists():
        return
    if comic_pks := volume_year_comics():
        queue.put(ForceUpdateComicsTask(comic_pks=comic_pks))
    # The migration cleared matches that may have been another volume's,
    # and year-named volumes match now, so look before the nightly rematch.
    queue.put(ReadingListRematchTask())
    Timestamp.objects.filter(key=_KEY).update(value="")


# A volume number this big is a year, as a CBL's Volume="2006" is.
_YEAR_LIKE_VOLUME = 1900


def _whole(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


class FoldedSeries:
    """The series with more than one volume, by exact name: years and ids."""

    def __init__(self) -> None:
        """Read the multi-volume series once."""
        multi_volume = (
            Volume.objects.values("series_id")
            .annotate(volumes=Count("pk"))
            .filter(volumes__gt=1)
            .values("series_id")
        )
        self.years: defaultdict[str, set[int]] = defaultdict(set)
        self.ids: defaultdict[str, set[tuple[str, str]]] = defaultdict(set)
        rows = Series.objects.filter(pk__in=multi_volume).values_list(
            "name", "start_year", "identifier__source__name", "identifier__key"
        )
        for name, start_year, id_source, id_key in rows:
            if start_year:
                self.years[name].add(start_year)
            if id_source and id_key:
                self.ids[name].add((id_source, str(id_key)))


def _drop_series_ids(series: dict, ids: set[tuple[str, str]]) -> None:
    identifiers = series.get("identifiers") or {}
    for source, identifier in tuple(identifiers.items()):
        if (source, str((identifier or {}).get("key"))) in ids:
            del identifiers[source]
    if "identifiers" in series and not identifiers:
        del series["identifiers"]


def _unfold_built_series(
    series: dict, name: str, start_year: int | None, folded: FoldedSeries
) -> None:
    """Drop the start year and ids codex folded into a built series."""
    if start_year is not None and start_year in folded.years.get(name, ()):
        del series["start_year"]
    if ids := folded.ids.get(name):
        _drop_series_ids(series, ids)


def unfold_reference(
    reference: Mapping[str, Any], folded: FoldedSeries, *, built: bool
) -> dict[str, Any]:
    """
    Return a reference without the series' start year codex folded into it.

    Migration 0062's first and third rules, for references restored from a
    dump made before it. A year-like volume that differs from the start
    year is a codex reference: no source writes that shape, so the year
    goes. A reference codex built (``built``) with no year-like volume
    loses a start year and series ids that a same-named series with more
    than one volume holds.
    """
    unfolded = deepcopy(dict(reference))
    if not isinstance(series := unfolded.get("series"), dict):
        return unfolded
    start_year = _whole(series.get("start_year"))
    volume = _whole((unfolded.get("volume") or {}).get("number"))
    if volume is not None and volume >= _YEAR_LIKE_VOLUME:
        if start_year is not None and volume != start_year:
            del series["start_year"]
    elif built and (name := series.get("name")):
        _unfold_built_series(series, name, start_year, folded)
    return unfolded

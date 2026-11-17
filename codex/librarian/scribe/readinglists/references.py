"""
Comicbox-shaped references to library comics.

A reading list entry names an issue in comicbox's own vocabulary: series,
volume, issue, date and issue ids. Codex builds the same shape for its
comics, so an entry that came from a comic's tags can find that comic
again after it is removed and re-added, and so lists from tags combine
and compare with fetched lists. The references are JSON-safe: issues are
strings, dates are their parts.
"""

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal
from itertools import batched
from typing import Any, Final

from codex.models import Comic
from codex.models.identifier import IdentifierType

# Below SQLite's bound-parameter limit with room for the rest of a query.
_PK_BATCH: Final = 10000
_COMIC_FIELDS: Final = (
    "pk",
    "series__name",
    "series__start_year",
    "series__identifier__source__name",
    "series__identifier__key",
    "volume__name",
    "issue_number",
    "issue_suffix",
    "year",
    "month",
    "day",
)


def issue_name(number: Decimal | None, suffix: str | None) -> str:
    """Render an issue as comicbox names one: ``10``, ``1.5``, ``2a``, ``-1``."""
    text = "" if number is None else format(number.normalize(), "f")
    return f"{text}{suffix or ''}"


def _series(name, start_year, id_source, id_key) -> dict[str, Any]:
    series: dict[str, Any] = {}
    if name:
        series["name"] = name
    if start_year:
        series["start_year"] = start_year
    if id_source and id_key:
        series["identifiers"] = {id_source: {"key": id_key}}
    return series


def _date(year, month, day) -> dict[str, int]:
    return {
        key: value
        for key, value in (("year", year), ("month", month), ("day", day))
        if value
    }


def _reference(row: tuple, identifiers: dict[str, dict]) -> dict[str, Any]:
    (
        _pk,
        series_name,
        start_year,
        id_source,
        id_key,
        volume,
        number,
        suffix,
        year,
        month,
        day,
    ) = row
    reference: dict[str, Any] = {}
    if series := _series(series_name, start_year, id_source, id_key):
        reference["series"] = series
    if volume is not None:
        reference["volume"] = {"number": volume}
    if issue := issue_name(number, suffix):
        reference["issue"] = {"name": issue}
    if date := _date(year, month, day):
        reference["date"] = date
    if identifiers:
        reference["identifiers"] = identifiers
    return reference


def _issue_identifiers(pks: tuple[int, ...]) -> dict[int, dict[str, dict]]:
    """Map each comic to its issue ids, ``{source: {"key": key}}``."""
    through = Comic.identifiers.through
    rows = (
        through.objects.filter(
            comic_id__in=pks,
            identifier__id_type=IdentifierType.ISSUE.value,
            identifier__source__isnull=False,
        )
        .order_by("comic_id", "identifier__source__name", "identifier__key")
        .values_list("comic_id", "identifier__source__name", "identifier__key")
    )
    identifiers: dict[int, dict[str, dict]] = defaultdict(dict)
    for comic_pk, source, key in rows:
        identifiers[comic_pk].setdefault(source, {"key": key})
    return identifiers


def comic_references(comic_pks: Iterable[int]) -> dict[int, dict[str, Any]]:
    """Return a comicbox reading-list entry for each comic, by pk."""
    references: dict[int, dict[str, Any]] = {}
    for batch in batched(sorted(set(comic_pks)), _PK_BATCH):
        identifiers = _issue_identifiers(batch)
        rows = Comic.objects.filter(pk__in=batch).values_list(*_COMIC_FIELDS)
        for row in rows:
            pk = row[0]
            references[pk] = _reference(row, identifiers.get(pk, {}))
    return references

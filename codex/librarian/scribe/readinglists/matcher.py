"""
Match reading list entries to library comics.

The first rule to find a comic wins, and the rule is stored on the entry:

1. A saved series mapping: the entry's series was mapped to a library
   series in review; look for the issue there.
2. comicbox's own matcher (``match_comics``) over the comics that could
   match: issue ids first, then series name with start year or volume and
   issue, then name with cover year and issue, then name variants. It
   vetoes a comic with a differing id from one database or a cover year
   more than one off, so codex applies the CLI's rules.
3. The series id with the issue number. A series stores only its best
   ranked identifier, so this works only when list and library share it.

Candidates are found in the database first, so the matcher sees only the
comics of series whose name could match and the comics an id names. A
deterministic best is taken among several and the entry is flagged for
review when they span more than one series or comicbox calls the match
ambiguous. Matching ignores per-user visibility; reading a list applies it.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from itertools import batched
from types import MappingProxyType
from typing import Any, Final

from comicbox.readinglists import name_variants, normalize_series, parse_issue
from comicbox.readinglists.match import FoundBy, match_comics
from django.db.models import Count, Max

from codex.librarian.scribe.readinglists.references import (
    comic_candidates,
    typed_reference,
)
from codex.models import Comic, Series
from codex.models.identifier import IdentifierType
from codex.models.readinglist import ReadingListMatchTier, ReadingListSeriesMapping

YEAR_LIKE_VOLUME: Final = 1900
_BATCH: Final = 500
_FOUND_BY_TIER: Final = MappingProxyType(
    {
        FoundBy.ID: ReadingListMatchTier.ISSUE_ID,
        FoundBy.NAME: ReadingListMatchTier.EXACT_NAME,
        FoundBy.NAME_YEAR: ReadingListMatchTier.EXACT_NAME,
        FoundBy.VARIANT: ReadingListMatchTier.NORMALIZED_NAME,
    }
)


@dataclass(frozen=True, slots=True)
class EntryMatch:
    """The comic an entry matched, how, and whether a person should look."""

    comic_pk: int | None = None
    tier: str = ReadingListMatchTier.NONE
    needs_review: bool = False


NO_MATCH: Final = EntryMatch()


def series_key(reference: Mapping[str, Any]) -> tuple[str, int] | None:
    """
    Return the key a series mapping is saved under: name and year.

    The year is the series start year, else a year-like volume, else 0.
    """
    series = reference.get("series") or {}
    if not (name := series.get("name")):
        return None
    year = series.get("start_year") or 0
    volume = (reference.get("volume") or {}).get("number") or 0
    if not year and volume >= YEAR_LIKE_VOLUME:
        year = volume
    return normalize_series(name), int(year)


IssueKey = tuple[Decimal | None, str]


def _issue_key(reference: Mapping[str, Any]) -> IssueKey | None:
    """Return a reference's issue number and suffix, as comics store them."""
    issue = reference.get("issue") or {}
    parsed = parse_issue(issue.get("name") or issue.get("number"))
    if parsed.number is None and not parsed.suffix:
        return None
    return parsed.number, parsed.suffix.casefold()


def _comics_by_issue(series_pks: Iterable[int]) -> dict[tuple[int, IssueKey], int]:
    """
    Map each comic of the series to ``(series, issue) -> lowest comic pk``.

    One query per batch of series, so matching a whole list by series and
    issue costs no query per entry.
    """
    found: dict[tuple[int, IssueKey], int] = {}
    for batch in batched(sorted(set(series_pks)), _BATCH):
        rows = Comic.objects.filter(series_id__in=batch).values_list(
            "pk", "series_id", "issue_number", "issue_suffix"
        )
        for pk, series_pk, number, suffix in rows:
            key = (series_pk, (number, (suffix or "").casefold()))
            if key not in found or pk < found[key]:
                found[key] = pk
    return found


def _best_of(
    found: Mapping[tuple[int, IssueKey], int],
    series_pks: Iterable[int],
    issue: IssueKey,
) -> int | None:
    """Return the lowest pk among the series' comics of that issue."""
    pks = (found.get((series_pk, issue)) for series_pk in series_pks)
    return min((pk for pk in pks if pk is not None), default=None)


class SeriesNameIndex:
    """Library series by every name variant; read-only, so it can be shared."""

    def __init__(self) -> None:
        """Index every series name's variants."""
        by_variant: defaultdict[str, set[int]] = defaultdict(set)
        for pk, name in Series.objects.values_list("pk", "name"):
            if not name:
                continue
            for variant in name_variants({"series": {"name": name}}):
                by_variant[variant].add(pk)
        self.by_variant: Mapping[str, frozenset[int]] = MappingProxyType(
            {variant: frozenset(pks) for variant, pks in by_variant.items()}
        )

    def series_for(self, reference: Mapping[str, Any]) -> set[int]:
        """Return the series whose names could be the reference's series."""
        if not (reference.get("series") or {}).get("name"):
            return set()
        pks: set[int] = set()
        for variant in name_variants(reference):
            pks |= self.by_variant.get(variant, frozenset())
        return pks


@lru_cache(maxsize=1)
def _series_index(_series_state: tuple[Any, ...]) -> SeriesNameIndex:
    """Build the index for one state of the series table."""
    return SeriesNameIndex()


def library_series_index() -> SeriesNameIndex:
    """
    Return the series index, built again only when the series change.

    Series are added and deleted, never renamed in place, so their count,
    highest pk and latest update tell whether the table changed: one
    aggregate query instead of normalizing every series name again.
    """
    state = Series.objects.aggregate(
        count=Count("pk"), last_pk=Max("pk"), updated=Max("updated_at")
    )
    return _series_index(tuple(state.values()))


class ListMatcher:
    """Match the entries of lists; reusable across the lists of one run."""

    def __init__(self) -> None:
        """Build the series index lazily, on the first list with names."""
        self._series_index: SeriesNameIndex | None = None
        self._mappings: dict[tuple[str, int], int] | None = None

    @property
    def series_index(self) -> SeriesNameIndex:
        """The library's series by name variant."""
        if self._series_index is None:
            self._series_index = library_series_index()
        return self._series_index

    @property
    def mappings(self) -> dict[tuple[str, int], int]:
        """Saved series mappings, ``(name key, year) -> series pk``."""
        if self._mappings is None:
            self._mappings = {
                (key, year): series_pk
                for key, year, series_pk in ReadingListSeriesMapping.objects.values_list(
                    "series_key", "year", "series_id"
                )
            }
        return self._mappings

    # 1. Series mappings.

    def _mapped_series(self, reference: Mapping[str, Any]) -> int | None:
        if (key := series_key(reference)) is None:
            return None
        return self.mappings.get(key) or self.mappings.get((key[0], 0))

    def _match_mapped(
        self, references: Sequence[Mapping[str, Any]], results: list[EntryMatch | None]
    ) -> None:
        if not self.mappings:
            return
        wanted: list[tuple[int, int, IssueKey]] = []
        for position, reference in enumerate(references):
            if results[position] is not None:
                continue
            series_pk = self._mapped_series(reference)
            issue = _issue_key(reference)
            if series_pk is not None and issue is not None:
                wanted.append((position, series_pk, issue))
        if not wanted:
            return
        found = _comics_by_issue(series_pk for _, series_pk, _ in wanted)
        for position, series_pk, issue in wanted:
            if (comic_pk := _best_of(found, (series_pk,), issue)) is not None:
                results[position] = EntryMatch(comic_pk, ReadingListMatchTier.MAPPING)

    # 2. comicbox's matcher.

    @staticmethod
    def _id_candidates(references: Iterable[Mapping[str, Any]]) -> set[int]:
        keys: defaultdict[str, set[str]] = defaultdict(set)
        for reference in references:
            for source, identifier in (reference.get("identifiers") or {}).items():
                if key := (identifier or {}).get("key"):
                    keys[source].add(str(key))
        pks: set[int] = set()
        for source, source_keys in keys.items():
            for batch in batched(sorted(source_keys), _BATCH):
                pks |= set(
                    Comic.objects.filter(
                        identifiers__source__name=source,
                        identifiers__id_type=IdentifierType.ISSUE.value,
                        identifiers__key__in=batch,
                    ).values_list("pk", flat=True)
                )
        return pks

    def _name_candidates(self, references: Iterable[Mapping[str, Any]]) -> set[int]:
        series_pks: set[int] = set()
        for reference in references:
            series_pks |= self.series_index.series_for(reference)
        pks: set[int] = set()
        for batch in batched(sorted(series_pks), _BATCH):
            pks |= set(
                Comic.objects.filter(series_id__in=batch).values_list("pk", flat=True)
            )
        return pks

    @staticmethod
    def _pick(found, series_of: Mapping[int, int | None]) -> EntryMatch:
        """Choose among the comics comicbox found for one entry."""
        sure = [comic for comic in found.comics if not comic.ambiguous]
        pool = sure or list(found.comics)
        strongest = min(pool, key=lambda comic: list(FoundBy).index(comic.by))
        best = [comic.path for comic in pool if comic.by == strongest.by]
        comic_pk = min(best)
        series = {series_of.get(pk) for pk in best}
        needs_review = not sure or len(series) > 1
        return EntryMatch(comic_pk, _FOUND_BY_TIER[strongest.by], needs_review)

    def _match_comicbox(
        self, references: Sequence[Mapping[str, Any]], results: list[EntryMatch | None]
    ) -> None:
        open_positions = [i for i, result in enumerate(results) if result is None]
        if not open_positions:
            return
        open_references = [references[i] for i in open_positions]
        candidate_pks = self._id_candidates(open_references) | self._name_candidates(
            open_references
        )
        if not candidate_pks:
            return
        candidates = comic_candidates(candidate_pks)
        series_of = dict(
            Comic.objects.filter(pk__in=candidate_pks).values_list("pk", "series_id")
        )
        entries = [typed_reference(reference) for reference in open_references]
        # comicbox types the keys as paths; any sortable key works, and pks
        # keep the lowest-pk choice deterministic.
        result = match_comics({"entries": entries}, candidates)  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]
        for found in result.found:
            results[open_positions[found.position]] = self._pick(found, series_of)

    # 3. Series id and issue.

    @staticmethod
    def _series_ids(reference: Mapping[str, Any]) -> set[tuple[str, str]]:
        """Return a reference's series ids as ``(source, key)``."""
        series_ids = (reference.get("series") or {}).get("identifiers") or {}
        return {
            (source, str(key))
            for source, identifier in series_ids.items()
            if (key := (identifier or {}).get("key"))
        }

    @staticmethod
    def _library_series(ids: set[tuple[str, str]]) -> dict[tuple[str, str], set[int]]:
        """Map each series id to the library series that carry it."""
        keys: defaultdict[str, set[str]] = defaultdict(set)
        for source, key in ids:
            keys[source].add(key)
        series: defaultdict[tuple[str, str], set[int]] = defaultdict(set)
        for source, source_keys in keys.items():
            for batch in batched(sorted(source_keys), _BATCH):
                rows = Series.objects.filter(
                    identifier__source__name=source, identifier__key__in=batch
                ).values_list("pk", "identifier__key")
                for series_pk, key in rows:
                    series[(source, key)].add(series_pk)
        return series

    @classmethod
    def _wanted_by_series_id(
        cls, references: Sequence[Mapping[str, Any]], results: list[EntryMatch | None]
    ) -> list[tuple[int, set[tuple[str, str]], IssueKey]]:
        """Return the open entries that carry series ids and an issue."""
        wanted: list[tuple[int, set[tuple[str, str]], IssueKey]] = []
        for position, reference in enumerate(references):
            if results[position] is not None:
                continue
            ids = cls._series_ids(reference)
            issue = _issue_key(reference)
            if ids and issue is not None:
                wanted.append((position, ids, issue))
        return wanted

    @classmethod
    def _match_series_ids(
        cls, references: Sequence[Mapping[str, Any]], results: list[EntryMatch | None]
    ) -> None:
        if not (wanted := cls._wanted_by_series_id(references, results)):
            return
        library = cls._library_series(set().union(*(ids for _, ids, _ in wanted)))
        found = _comics_by_issue(pk for pks in library.values() for pk in pks)
        for position, ids, issue in wanted:
            series_pks = set().union(*(library.get(id_, set()) for id_ in ids))
            if (comic_pk := _best_of(found, series_pks, issue)) is not None:
                results[position] = EntryMatch(comic_pk, ReadingListMatchTier.SERIES_ID)

    def match(self, references: Sequence[Mapping[str, Any]]) -> list[EntryMatch]:
        """Match a list's references, in list order, to comics."""
        results: list[EntryMatch | None] = [None] * len(references)
        self._match_mapped(references, results)
        self._match_comicbox(references, results)
        self._match_series_ids(references, results)
        return [result or NO_MATCH for result in results]

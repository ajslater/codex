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
from itertools import batched
from types import MappingProxyType
from typing import Any, Final

from comicbox.readinglists import name_variants, normalize_series, parse_issue
from comicbox.readinglists.match import FoundBy, match_comics
from django.db.models import Q

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


def _issue_q(reference: Mapping[str, Any]) -> Q | None:
    """Return the comic filter for a reference's issue number and suffix."""
    issue = reference.get("issue") or {}
    parsed = parse_issue(issue.get("name") or issue.get("number"))
    if parsed.number is None and not parsed.suffix:
        return None
    return Q(issue_number=parsed.number, issue_suffix__iexact=parsed.suffix)


def _best(pks: Iterable[int]) -> int | None:
    return min(pks, default=None)


class SeriesNameIndex:
    """Library series by every name variant, built once per run."""

    def __init__(self) -> None:
        """Index every series name's variants."""
        self.by_variant: defaultdict[str, set[int]] = defaultdict(set)
        for pk, name in Series.objects.values_list("pk", "name"):
            if not name:
                continue
            for variant in name_variants({"series": {"name": name}}):
                self.by_variant[variant].add(pk)

    def series_for(self, reference: Mapping[str, Any]) -> set[int]:
        """Return the series whose names could be the reference's series."""
        if not (reference.get("series") or {}).get("name"):
            return set()
        pks: set[int] = set()
        for variant in name_variants(reference):
            pks |= self.by_variant.get(variant, set())
        return pks


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
            self._series_index = SeriesNameIndex()
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
        for position, reference in enumerate(references):
            if results[position] is not None:
                continue
            series_pk = self._mapped_series(reference)
            issue_q = _issue_q(reference)
            if series_pk is None or issue_q is None:
                continue
            pks = Comic.objects.filter(issue_q, series_id=series_pk).values_list(
                "pk", flat=True
            )
            if (comic_pk := _best(pks)) is not None:
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
    def _series_id_q(reference: Mapping[str, Any]) -> Q:
        """Return the comic filter for a reference's series ids."""
        series_ids = (reference.get("series") or {}).get("identifiers") or {}
        series_q = Q()
        for source, identifier in series_ids.items():
            if key := (identifier or {}).get("key"):
                series_q |= Q(
                    series__identifier__source__name=source,
                    series__identifier__key=str(key),
                )
        return series_q

    @classmethod
    def _series_id_match(cls, reference: Mapping[str, Any]) -> EntryMatch | None:
        series_q = cls._series_id_q(reference)
        issue_q = _issue_q(reference)
        if not series_q or issue_q is None:
            return None
        pks = Comic.objects.filter(series_q, issue_q).values_list("pk", flat=True)
        if (comic_pk := _best(pks)) is None:
            return None
        return EntryMatch(comic_pk, ReadingListMatchTier.SERIES_ID)

    @classmethod
    def _match_series_ids(
        cls, references: Sequence[Mapping[str, Any]], results: list[EntryMatch | None]
    ) -> None:
        for position, reference in enumerate(references):
            if results[position] is None:
                results[position] = cls._series_id_match(reference)

    def match(self, references: Sequence[Mapping[str, Any]]) -> list[EntryMatch]:
        """Match a list's references, in list order, to comics."""
        results: list[EntryMatch | None] = [None] * len(references)
        self._match_mapped(references, results)
        self._match_comicbox(references, results)
        self._match_series_ids(references, results)
        return [result or NO_MATCH for result in results]

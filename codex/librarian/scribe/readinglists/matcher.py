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

A codex series is a name and holds every volume of it, so the mapping
and series-id rules look for the issue in each volume, keep the volumes
that agree with the entry's start year or volume, then those of its
cover year, and flag review when volumes that differ are left.

Candidates are found in the database first, so the matcher sees only the
comics of series whose name could match and the comics an id names. A
deterministic best is taken among several and the entry is flagged for
review when they span more than one series or volume, or comicbox calls
the match ambiguous. An entry left missing whose issue comicbox refused
as another volume's, or for its cover year, keeps that comic as a
suggestion and is flagged for review instead of looking absent from the
library. Matching ignores per-user visibility; reading a list applies it.
"""

from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from itertools import batched
from types import MappingProxyType
from typing import Any, Final

from comicbox.readinglists import (
    Discriminators,
    discriminators,
    name_variants,
    normalize_series,
    parse_issue,
)
from comicbox.readinglists.identity import any_conflict
from comicbox.readinglists.match import FoundBy, Refused, RefusedReason, match_comics
from django.db.models import Count, Max

from codex.librarian.scribe.readinglists.references import (
    PK_BATCH,
    comic_candidates,
    typed_reference,
)
from codex.models import Comic, Series
from codex.models.identifier import IdentifierType
from codex.models.readinglist import ReadingListMatchTier, ReadingListSeriesMapping

_BATCH: Final = 500
_FOUND_BY_TIER: Final = MappingProxyType(
    {
        FoundBy.ID: ReadingListMatchTier.ISSUE_ID,
        FoundBy.NAME: ReadingListMatchTier.EXACT_NAME,
        FoundBy.NAME_YEAR: ReadingListMatchTier.EXACT_NAME,
        FoundBy.VARIANT: ReadingListMatchTier.NORMALIZED_NAME,
    }
)


# A refused comic's preference as a suggestion: another volume's issue of
# the same cover year before a cover year more than one off.
_REFUSED_ORDER: Final = (RefusedReason.OTHER_VOLUME, RefusedReason.COVER_YEAR)


@dataclass(frozen=True, slots=True)
class EntryMatch:
    """
    The comic an entry matched, how, and whether a person should look.

    A missing entry may carry ``suggested_pk``, a comic the matcher refused
    that a person may know is the one; it is then flagged for review.
    """

    comic_pk: int | None = None
    tier: str = ReadingListMatchTier.NONE
    needs_review: bool = False
    suggested_pk: int | None = None


NO_MATCH: Final = EntryMatch()


def series_key(reference: Mapping[str, Any]) -> tuple[str, int] | None:
    """
    Return the key a series mapping is saved under: name and year.

    The year is the series start year, else a year-like volume, else 0.
    """
    series = reference.get("series") or {}
    if not (name := series.get("name")):
        return None
    return normalize_series(name), int(discriminators(reference).year or 0)


IssueKey = tuple[Decimal | None, str]


def _issue_key(reference: Mapping[str, Any]) -> IssueKey | None:
    """Return a reference's issue number and suffix, as comics store them."""
    issue = reference.get("issue") or {}
    parsed = parse_issue(issue.get("name") or issue.get("number"))
    if parsed.number is None and not parsed.suffix:
        return None
    return parsed.number, parsed.suffix.casefold()


# A comic's preference among copies of one issue: live before pending
# delete, then lowest pk.
_Rank = tuple[bool, int]


@dataclass(frozen=True, slots=True)
class _Copy:
    """The best comic of one issue in one volume."""

    rank: _Rank
    cover_year: int | None
    volume: Discriminators


# A series' issue, by volume pk.
_Volumes = dict[int | None, _Copy]


def _volume_discriminators(name: int | None, start_year: int | None) -> Discriminators:
    """Tell a volume as comicbox tells a reference's, by name and start year."""
    reference: dict[str, Any] = {}
    if start_year:
        reference["series"] = {"start_year": start_year}
    if name is not None:
        reference["volume"] = {"number": name}
    return discriminators(reference)


def _comics_by_issue(
    series_pks: Iterable[int],
) -> dict[tuple[int, IssueKey], _Volumes]:
    """
    Map ``(series, issue)`` to the best comic of that issue in each volume.

    The best is a live comic before one pending delete, a moved file's old
    row, then the lowest pk. One query per batch of series, so matching a
    whole list by series and issue costs no query per entry.
    """
    found: dict[tuple[int, IssueKey], _Volumes] = defaultdict(dict)
    for batch in batched(sorted(set(series_pks)), _BATCH):
        rows = Comic.objects.filter(series_id__in=batch).values_list(
            "pk",
            "series_id",
            "issue_number",
            "issue_suffix",
            "missing_since",
            "year",
            "volume_id",
            "volume__name",
            "volume__start_year",
        )
        for row in rows:
            pk, series_pk, number, suffix, missing_since, year, volume_pk = row[:7]
            volumes = found[(series_pk, (number, (suffix or "").casefold()))]
            rank = (missing_since is not None, pk)
            if (copy := volumes.get(volume_pk)) is None or rank < copy.rank:
                volumes[volume_pk] = _Copy(rank, year, _volume_discriminators(*row[7:]))
    return found


def _of_cover_year(copies: list[_Copy], year: int | None) -> list[_Copy]:
    """Keep the copies of the cover year, else within a year of it, else all."""
    if year is None:
        return copies
    for slack in (0, 1):
        if near := [
            copy
            for copy in copies
            if copy.cover_year is not None and abs(copy.cover_year - year) <= slack
        ]:
            return near
    return copies


def _best_of(
    found: Mapping[tuple[int, IssueKey], _Volumes],
    series_pks: Iterable[int],
    reference: Mapping[str, Any],
    tier: str,
) -> EntryMatch | None:
    """
    Return the best of the series' comics of the reference's issue.

    The volumes that agree with the reference's start year or volume are
    kept, or every one when none does: a mapping or a series id already
    says which series it is. Then the ones of its cover year. Volumes that
    differ among those left are a guess, so the match is flagged.
    """
    if (issue := _issue_key(reference)) is None:
        return None
    copies = [
        copy
        for series_pk in series_pks
        for copy in found.get((series_pk, issue), {}).values()
    ]
    if not copies:
        return None
    wanted = discriminators(reference)
    copies = [copy for copy in copies if not wanted.conflicts(copy.volume)] or copies
    copies = _of_cover_year(copies, _cover_year(reference))
    best = min(copies, key=lambda copy: copy.rank)
    needs_review = any_conflict(copy.volume for copy in copies)
    return EntryMatch(best.rank[1], tier, needs_review)


def _cover_year(reference: Mapping[str, Any]) -> int | None:
    """Return a reference's cover year, from its year or its cover date."""
    date_ = typed_reference(reference).get("date") or {}
    if year := date_.get("year"):
        return int(year)
    cover_date = date_.get("cover_date")
    return cover_date.year if cover_date else None


def _live_first(pool: list, pending: Collection[int]) -> list:
    """Return the found comics not pending delete, or all if every one is."""
    return [comic for comic in pool if comic.path not in pending] or pool


def _series_and_pending(
    comic_pks: Collection[int],
) -> tuple[dict[int, int | None], set[int]]:
    """Return each comic's series, and the comics pending delete."""
    rows = [
        row
        for batch in batched(sorted(set(comic_pks)), PK_BATCH)
        for row in Comic.objects.filter(pk__in=batch).values_list(
            "pk", "series_id", "missing_since"
        )
    ]
    series_of = {pk: series_pk for pk, series_pk, _ in rows}
    pending = {pk for pk, _, missing_since in rows if missing_since is not None}
    return series_of, pending


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


def _strongest_finds(found, pending: Collection[int]) -> tuple[list, Any, list[int]]:
    """Return the sure finds, the strongest find and the pks tied with it."""
    sure = [comic for comic in found.comics if not comic.ambiguous]
    pool = sure or list(found.comics)
    strongest = min(pool, key=lambda comic: list(FoundBy).index(comic.by))
    tied = [comic for comic in pool if comic.by == strongest.by]
    return sure, strongest, [comic.path for comic in _live_first(tied, pending)]


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
        wanted: list[tuple[int, int]] = []
        for position, reference in enumerate(references):
            if results[position] is not None:
                continue
            series_pk = self._mapped_series(reference)
            if series_pk is not None and _issue_key(reference) is not None:
                wanted.append((position, series_pk))
        if not wanted:
            return
        found = _comics_by_issue(series_pk for _, series_pk in wanted)
        for position, series_pk in wanted:
            results[position] = _best_of(
                found, (series_pk,), references[position], ReadingListMatchTier.MAPPING
            )

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
    def _pick(
        found,
        series_of: Mapping[int, int | None],
        pending: Collection[int],
        candidates: Mapping[int, Mapping[str, Any]],
    ) -> EntryMatch:
        """
        Choose among the comics comicbox found for one entry.

        The strongest rule wins, then a live copy among its finds: a comic
        a weaker rule found never beats the list's own comic while that one
        is pending delete. Finds of more than one series, or of volumes
        that differ, are a guess. One run tagged both "v2" and "(2011)"
        sits in two volumes that do not differ.
        """
        sure, strongest, best = _strongest_finds(found, pending)
        comic_pk = min(best)
        series = {series_of.get(pk) for pk in best}
        volumes = (discriminators(candidates[pk]) for pk in best)
        needs_review = not sure or len(series) > 1 or any_conflict(volumes)
        return EntryMatch(comic_pk, _FOUND_BY_TIER[strongest.by], needs_review)

    @staticmethod
    def _suggest(
        refused: Iterable[Refused],
        open_positions: Sequence[int],
        pending: Collection[int],
        suggestions: dict[int, int],
    ) -> None:
        """Keep each missing entry's likeliest refused comic, live first."""
        best: dict[int, tuple[int, bool, int]] = {}
        for refusal in refused:
            # The candidates are keyed by pk, so the paths are pks.
            pk: int = refusal.path  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
            rank = (_REFUSED_ORDER.index(refusal.reason), pk in pending, pk)
            position = open_positions[refusal.position]
            if position not in best or rank < best[position]:
                best[position] = rank
        suggestions.update({position: rank[2] for position, rank in best.items()})

    def _match_comicbox(
        self,
        references: Sequence[Mapping[str, Any]],
        results: list[EntryMatch | None],
        suggestions: dict[int, int],
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
        series_of, pending = _series_and_pending(candidate_pks)
        entries = [typed_reference(reference) for reference in open_references]
        # comicbox types the keys as paths; any sortable key works, and pks
        # keep the lowest-pk choice deterministic.
        result = match_comics({"entries": entries}, candidates)  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]
        for found in result.found:
            results[open_positions[found.position]] = self._pick(
                found, series_of, pending, candidates
            )
        self._suggest(result.refused, open_positions, pending, suggestions)

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
    ) -> list[tuple[int, set[tuple[str, str]]]]:
        """Return the open entries that carry series ids and an issue."""
        wanted: list[tuple[int, set[tuple[str, str]]]] = []
        for position, reference in enumerate(references):
            if results[position] is not None:
                continue
            ids = cls._series_ids(reference)
            if ids and _issue_key(reference) is not None:
                wanted.append((position, ids))
        return wanted

    @classmethod
    def _match_series_ids(
        cls, references: Sequence[Mapping[str, Any]], results: list[EntryMatch | None]
    ) -> None:
        if not (wanted := cls._wanted_by_series_id(references, results)):
            return
        library = cls._library_series(set().union(*(ids for _, ids in wanted)))
        found = _comics_by_issue(pk for pks in library.values() for pk in pks)
        for position, ids in wanted:
            series_pks = set().union(*(library.get(id_, set()) for id_ in ids))
            results[position] = _best_of(
                found, series_pks, references[position], ReadingListMatchTier.SERIES_ID
            )

    def match(self, references: Sequence[Mapping[str, Any]]) -> list[EntryMatch]:
        """Match a list's references, in list order, to comics."""
        results: list[EntryMatch | None] = [None] * len(references)
        suggestions: dict[int, int] = {}
        self._match_mapped(references, results)
        self._match_comicbox(references, results, suggestions)
        self._match_series_ids(references, results)
        return [
            result
            or (
                EntryMatch(needs_review=True, suggested_pk=suggestions[position])
                if position in suggestions
                else NO_MATCH
            )
            for position, result in enumerate(results)
        ]

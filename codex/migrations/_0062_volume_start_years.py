"""
Migration 0062's data step: start years move from series to volumes.

Kept apart so the migration stays readable; the loader skips modules whose
name starts with an underscore. It reads historical models only, and is
frozen with the migration.

A codex series is a name, but a comicbox series is one volume run, and the
importer folded every volume's start year into the one ``Series`` row. So:

1. A series with one volume gives it its start year, unless the volume is
   named for another year.
2. Reading list references codex built carry the folded year. They are
   rewritten by three rules, and the series ids of a series with more than
   one volume go from them too.
3. Name and id matches that may have taken another volume's issue are
   cleared, so a rematch finds them again.
4. The librarian is told to re-read one comic of each volume, once, to
   learn the volumes' start years, and to match the lists again.
"""

from collections import defaultdict
from copy import deepcopy
from itertools import batched

# A volume number this big is a year, as a CBL's Volume="2006" is.
_YEAR_LIKE_VOLUME = 1900
_BATCH = 1000
# Values bound per query: a stock SQLite allows 32,766 variables.
_PK_BATCH = 10000
# The tiers whose references codex built from a comic.
_BUILT_TIERS = frozenset({"tagged"})
# The tiers that may have picked the lowest pk among a series' volumes.
_RESET_TIERS = ("exact_name", "normalized_name", "mapping", "series_id")
_VOLUME_START_YEARS = "VY"
_PENDING = "pending"


def _whole(value) -> int | None:
    """Return a reference's number as an int, or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def _start_year(reference: dict) -> int | None:
    return _whole((reference.get("series") or {}).get("start_year"))


def _volume_number(reference: dict) -> int | None:
    return _whole((reference.get("volume") or {}).get("number"))


def _drop_start_year(reference: dict) -> None:
    (reference.get("series") or {}).pop("start_year", None)


def _set_start_year(reference: dict, year: int | None) -> None:
    if year is None:
        _drop_start_year(reference)
    else:
        reference.setdefault("series", {})["start_year"] = year


def _drop_series_ids(reference: dict, ids: set[tuple[str, str]]) -> None:
    """Remove the series ids codex gave a reference from a folded series."""
    series = reference.get("series") or {}
    identifiers = series.get("identifiers") or {}
    for source, identifier in tuple(identifiers.items()):
        if (source, str((identifier or {}).get("key"))) in ids:
            del identifiers[source]
    if "identifiers" in series and not identifiers:
        del series["identifiers"]


class _Library:
    """What the rules need to know about the library's series and volumes."""

    def __init__(self, apps) -> None:
        series_model = apps.get_model("codex", "series")
        volume_model = apps.get_model("codex", "volume")
        counts: defaultdict[int, int] = defaultdict(int)
        for series_pk in volume_model.objects.values_list("series_id", flat=True):
            counts[series_pk] += 1
        self.multi_volume = frozenset(pk for pk, count in counts.items() if count > 1)
        self.series_year: dict[int, int | None] = {}
        self.series_id: dict[int, tuple[str, str]] = {}
        # Multi-volume series by exact name and start year, with their ids.
        self.multi_by_name: defaultdict[str, list[tuple[int | None, int]]] = (
            defaultdict(list)
        )
        rows = series_model.objects.values_list(
            "pk", "name", "start_year", "identifier__source__name", "identifier__key"
        )
        for pk, name, start_year, id_source, id_key in rows:
            self.series_year[pk] = start_year
            if id_source and id_key:
                self.series_id[pk] = (id_source, str(id_key))
            if pk in self.multi_volume:
                self.multi_by_name[name].append((start_year, pk))
        self._counts = counts

    def backfill(self, apps) -> None:
        """Give each series' only volume the series' start year."""
        volume_model = apps.get_model("codex", "volume")
        single = [
            pk
            for pk, count in self._counts.items()
            if count == 1 and self.series_year.get(pk)
        ]
        updates = []
        for batch in batched(single, _PK_BATCH):
            for volume in volume_model.objects.filter(series_id__in=batch).only(
                "pk", "name", "series_id"
            ):
                year = self.series_year[volume.series_id]
                name = volume.name
                if name is not None and name >= _YEAR_LIKE_VOLUME and name != year:
                    # Named for another year: the series' may be a deleted
                    # volume's.
                    continue
                volume.start_year = year
                updates.append(volume)
        volume_model.objects.bulk_update(updates, ("start_year",), batch_size=_BATCH)

    def multi_named(self, reference: dict) -> list[tuple[int | None, int]]:
        name = (reference.get("series") or {}).get("name")
        return self.multi_by_name.get(name, []) if name else []


def _rule_1(reference: dict) -> None:
    """Drop a start year that a year-like volume contradicts."""
    volume = _volume_number(reference)
    start_year = _start_year(reference)
    if (
        volume is not None
        and volume >= _YEAR_LIKE_VOLUME
        and start_year is not None
        and volume != start_year
    ):
        _drop_start_year(reference)


def _rule_2(reference: dict, library: _Library, comic: tuple) -> None:
    """Give a linked entry its comic's volume's year for the series'."""
    series_pk, volume_year = comic
    start_year = _start_year(reference)
    if start_year is not None and start_year == library.series_year.get(series_pk):
        _set_start_year(reference, volume_year)
    if series_pk in library.multi_volume and (
        series_id := library.series_id.get(series_pk)
    ):
        _drop_series_ids(reference, {series_id})


def _rule_3(reference: dict, library: _Library) -> None:
    """Drop an unlinked entry's year when a same-named folded series has it."""
    if not (named := library.multi_named(reference)):
        return
    start_year = _start_year(reference)
    if start_year is not None and any(year == start_year for year, _ in named):
        _drop_start_year(reference)
    ids = {library.series_id[pk] for _, pk in named if pk in library.series_id}
    if ids:
        _drop_series_ids(reference, ids)


def rewrite_reference(
    reference: dict,
    library: _Library,
    *,
    built: bool,
    comic: tuple | None,
) -> dict:
    """Return the reference without the start years and ids codex folded."""
    reference = deepcopy(reference)
    _rule_1(reference)
    volume = _volume_number(reference)
    if not built or (volume is not None and volume >= _YEAR_LIKE_VOLUME):
        return reference
    if comic is not None:
        _rule_2(reference, library, comic)
    else:
        _rule_3(reference, library)
    return reference


def _comics(apps, comic_pks: set[int]) -> dict[int, tuple]:
    """Map each comic to its series and its volume's start year."""
    comic_model = apps.get_model("codex", "comic")
    comics: dict[int, tuple] = {}
    for batch in batched(sorted(comic_pks), _PK_BATCH):
        rows = comic_model.objects.filter(pk__in=batch).values_list(
            "pk", "series_id", "volume__start_year"
        )
        for pk, series_pk, volume_year in rows:
            comics[pk] = (series_pk, volume_year)
    return comics


def _rewrite_references(apps, library: _Library) -> None:
    entry_model = apps.get_model("codex", "readinglistentry")
    entries = (
        entry_model.objects.exclude(reference={})
        .only("pk", "reference", "comic_id", "manual", "match_tier")
        .order_by("pk")
    )
    for batch in batched(entries.iterator(chunk_size=_BATCH), _BATCH):
        comics = _comics(apps, {e.comic_id for e in batch if e.comic_id})
        changed = []
        for entry in batch:
            if not isinstance(entry.reference, dict):
                continue
            built = entry.manual or entry.match_tier in _BUILT_TIERS
            comic = comics.get(entry.comic_id) if entry.comic_id else None
            reference = rewrite_reference(
                entry.reference, library, built=built, comic=comic
            )
            if reference != entry.reference:
                entry.reference = reference
                changed.append(entry)
        entry_model.objects.bulk_update(changed, ("reference",), batch_size=_BATCH)


def _reset_matches(apps, library: _Library) -> None:
    """Clear name and id matches in series with more than one volume."""
    entry_model = apps.get_model("codex", "readinglistentry")
    for batch in batched(sorted(library.multi_volume), _PK_BATCH):
        entry_model.objects.filter(
            manual=False,
            ignored=False,
            live_source__isnull=True,
            match_tier__in=_RESET_TIERS,
            comic__series_id__in=batch,
        ).update(comic=None, match_tier="", needs_review=False)


def _mark_pending(apps) -> None:
    timestamp_model = apps.get_model("codex", "timestamp")
    timestamp_model.objects.update_or_create(
        key=_VOLUME_START_YEARS, defaults={"value": _PENDING}
    )


def volume_start_years(apps, _schema_editor) -> None:
    """Move start years to volumes and clean up what the folding left."""
    library = _Library(apps)
    library.backfill(apps)
    _rewrite_references(apps, library)
    _reset_matches(apps, library)
    _mark_pending(apps)

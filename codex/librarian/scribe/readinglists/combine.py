"""
Recompute a reading list from its sources.

comicbox combines the sources' documents in rank order: the first ordered
source is the backbone whose order never moves, entries other sources add
go beside their neighbours, and every id any source knows is merged onto
each entry. Codex then maps the combined entries back to comics and keeps
what people did by hand:

- A row from the tags source is its comic: matched by definition.
- Hand edits are an overlay keyed by the entry's identity,
  ``(entry_keys(entry)[0], occurrence)``: a hand-picked comic and a hidden
  entry survive any recompute. They are saved in Codex only.
- Entries added by hand go back after the entry they followed.
- A hand reorder locks the order: the current entries go first, so nothing
  moves, and entries new to the list are flagged for review.
- Every other entry goes through the matcher.

Removing a source recomputes the list without it, so a combination can be
undone.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from comicbox.readinglists import combine, entry_keys
from django.db import transaction

from codex.choices.limits import MAX_NAME_LEN
from codex.librarian.scribe.readinglists.documents import (
    ENTRIES_KEY,
    tags_document,
    to_json,
)
from codex.librarian.scribe.readinglists.matcher import ListMatcher
from codex.librarian.scribe.readinglists.references import (
    issue_name,
    typed_reference,
)
from codex.models import Comic
from codex.models.readinglist import (
    MAX_ISSUE_LEN,
    ReadingList,
    ReadingListEntry,
    ReadingListMatchTier,
    ReadingListSource,
    ReadingListSourceKind,
)

_BATCH: Final = 1000
# Header fields a recombine fills from the combined list, unless edited.
_HEADER_FIELDS: Final = (
    ("description", "description"),
    ("list_type", "list_type"),
    ("start_year", "start_year"),
    ("end_year", "end_year"),
    ("list_notes", "notes"),
)
_EXTRA_KEYS: Final = ("previous", "next", "tags")

OverlayKey = tuple[Any, int]


def overlay_keys(references: Sequence[Mapping[str, Any]]) -> list[OverlayKey | None]:
    """
    Return each entry's overlay key, ``(first identity key, occurrence)``.

    An issue a list reads twice is two entries; the occurrence tells them
    apart. An entry with no key cannot be found again and gets None.
    """
    seen: Counter = Counter()
    keys: list[OverlayKey | None] = []
    for reference in references:
        entry_key = next(iter(entry_keys(typed_reference(reference))), None)
        if entry_key is None:
            keys.append(None)
            continue
        keys.append((entry_key, seen[entry_key]))
        seen[entry_key] += 1
    return keys


@dataclass(slots=True)
class Overlay:
    """What people did to a list by hand, keyed by entry identity."""

    picked: dict[OverlayKey, int] = field(default_factory=dict)
    ignored: set[OverlayKey] = field(default_factory=set)
    # A hand-added entry and the key of the entry it followed.
    manual: list[tuple[OverlayKey | None, ReadingListEntry]] = field(
        default_factory=list
    )

    @classmethod
    def of(cls, entries: Sequence[ReadingListEntry]) -> "Overlay":
        """Read the hand edits off a list's current entries."""
        overlay = cls()
        keys = overlay_keys([entry.reference for entry in entries])
        previous: OverlayKey | None = None
        for entry, key in zip(entries, keys, strict=True):
            if entry.manual:
                overlay.manual.append((previous, entry))
                continue
            if key is not None:
                comic_pk = entry.comic_id  # pyright: ignore[reportAttributeAccessIssue]
                if entry.match_tier == ReadingListMatchTier.MANUAL.value and comic_pk:
                    overlay.picked[key] = comic_pk
                if entry.ignored:
                    overlay.ignored.add(key)
                previous = key
        return overlay


@dataclass(slots=True)
class _Input:
    document: dict[str, Any]
    source: ReadingListSource | None = None
    # For the tags source: the comic each row is.
    comics: list[int] | None = None


def _current_document(
    reading_list: ReadingList, entries: Sequence[ReadingListEntry], source_pks: set[int]
) -> dict[str, Any]:
    """Return the list as it stands, less what no source supplies any more."""
    kept = [
        entry.reference
        for entry in entries
        if not entry.manual
        and entry.reference
        and source_pks.intersection(entry.source_ids or ())
    ]
    return {"name": reading_list.name, ENTRIES_KEY: kept}


def _inputs(
    reading_list: ReadingList,
    sources: Sequence[ReadingListSource],
    entries: Sequence[ReadingListEntry],
) -> list[_Input]:
    inputs: list[_Input] = []
    if reading_list.order_locked:
        source_pks = {source.pk for source in sources}
        inputs.append(_Input(_current_document(reading_list, entries, source_pks)))
    for source in sources:
        if source.kind == ReadingListSourceKind.TAGS.value:
            tags = tags_document(source)
            inputs.append(_Input(tags.document, source, tags.comics))
        else:
            inputs.append(_Input(dict(source.document or {}), source))
    return inputs


@dataclass(slots=True)
class _Row:
    reference: dict[str, Any]
    source_ids: list[int]
    comic_pk: int | None = None
    tier: str = ReadingListMatchTier.NONE
    needs_review: bool = False
    ignored: bool = False
    entry_type: str = ""


def _row(
    reference: dict[str, Any],
    origins,
    inputs: Sequence[_Input],
    positions: Sequence[int],
) -> _Row:
    """Build one combined entry's row: its sources, and its comic from tags."""
    row = _Row(reference=reference, source_ids=[])
    for origin in origins:
        item = inputs[positions[origin.input_index]]
        if item.source is not None:
            row.source_ids.append(item.source.pk)
        if item.comics is not None and row.comic_pk is None:
            row.comic_pk = item.comics[origin.row]
            row.tier = ReadingListMatchTier.TAGGED
    row.entry_type = str(reference.get("entry_type") or "")
    return row


def _flagged(result, positions: Sequence[int], *, locked: bool) -> set[int]:
    """
    Return the combined positions a person should look at.

    Joins made on a name alone, ids that disagree, and in a locked list
    whatever the current order did not hold.
    """
    flagged = set(result.name_joins)
    flagged |= {conflict.entry for conflict in result.id_conflicts}
    if locked:
        flagged |= {
            index
            for index, origins in enumerate(result.provenance)
            if all(positions[origin.input_index] != 0 for origin in origins)
        }
    return flagged


def _combined_rows(
    inputs: Sequence[_Input], *, locked: bool
) -> tuple[list[_Row], dict]:
    """Combine the inputs and return a row per combined entry, plus the header."""
    documents = [item.document for item in inputs if item.document]
    if not documents:
        return [], {}
    positions = [index for index, item in enumerate(inputs) if item.document]
    result = combine(documents)
    combined = result.reading_list
    references = to_json(combined).get(ENTRIES_KEY, []) if combined else []
    flagged = _flagged(result, positions, locked=locked)
    rows: list[_Row] = []
    for index, reference in enumerate(references):
        row = _row(reference, result.provenance[index], inputs, positions)
        row.needs_review = index in flagged
        rows.append(row)
    return rows, combined


def _apply_overlay(rows: Sequence[_Row], overlay: Overlay) -> None:
    live = set(
        Comic.objects.filter(pk__in=overlay.picked.values()).values_list(
            "pk", flat=True
        )
    )
    keys = overlay_keys([row.reference for row in rows])
    for row, key in zip(rows, keys, strict=True):
        if key is None:
            continue
        if key in overlay.ignored:
            row.ignored = True
        picked = overlay.picked.get(key)
        if picked in live and row.tier != ReadingListMatchTier.TAGGED.value:
            row.comic_pk = picked
            row.tier = ReadingListMatchTier.MANUAL


def _match_rows(rows: Sequence[_Row], matcher: ListMatcher) -> None:
    open_rows = [row for row in rows if row.comic_pk is None]
    if not open_rows:
        return
    matches = matcher.match([row.reference for row in open_rows])
    for row, found in zip(open_rows, matches, strict=True):
        if found.comic_pk is None:
            continue
        row.comic_pk = found.comic_pk
        row.tier = found.tier
        row.needs_review = row.needs_review or found.needs_review


def _with_manual(
    rows: Sequence[_Row], overlay: Overlay
) -> list[_Row | ReadingListEntry]:
    """Put each hand-added entry back after the entry it followed."""
    if not overlay.manual:
        return list(rows)
    keys = overlay_keys([row.reference for row in rows])
    after: dict[OverlayKey | None, list[ReadingListEntry]] = {}
    for previous, entry in overlay.manual:
        target = previous if previous in keys else None
        after.setdefault(target, []).append(entry)
    ordered: list[_Row | ReadingListEntry] = list(after.pop(None, []))
    for row, key in zip(rows, keys, strict=True):
        ordered.append(row)
        ordered.extend(after.pop(key, []) if key is not None else [])
    return ordered


def _entry(reading_list: ReadingList, position: int, row: _Row) -> ReadingListEntry:
    reference = row.reference
    series = reference.get("series") or {}
    issue = reference.get("issue") or {}
    year = (reference.get("date") or {}).get("year")
    if year is None and (cover := (reference.get("date") or {}).get("cover_date")):
        year = int(str(cover)[:4])
    return ReadingListEntry(
        reading_list=reading_list,
        position=position,
        comic_id=row.comic_pk,
        reference=reference,
        series_name=str(series.get("name") or "")[:MAX_NAME_LEN],
        issue=str(issue.get("name") or issue_name(None, issue.get("suffix")))[
            :MAX_ISSUE_LEN
        ],
        year=year,
        match_tier=row.tier,
        needs_review=row.needs_review and row.comic_pk is not None,
        ignored=row.ignored,
        entry_type=row.entry_type[:32],
        source_ids=sorted(set(row.source_ids)),
    )


def _copy_manual(entry: ReadingListEntry, position: int) -> ReadingListEntry:
    """Return a hand-added entry again, at its new position."""
    return ReadingListEntry(
        reading_list_id=entry.reading_list_id,  # pyright: ignore[reportAttributeAccessIssue]
        position=position,
        comic_id=entry.comic_id,  # pyright: ignore[reportAttributeAccessIssue]
        reference=entry.reference,
        series_name=entry.series_name,
        issue=entry.issue,
        year=entry.year,
        match_tier=entry.match_tier,
        needs_review=entry.needs_review,
        ignored=entry.ignored,
        manual=True,
        entry_type=entry.entry_type,
        source_ids=entry.source_ids,
    )


def _update_header(reading_list: ReadingList, combined: Mapping[str, Any]) -> None:
    if not combined:
        return
    document = to_json(combined)
    edited: set[str] = set(reading_list.edited_fields or ())
    for attr, key in _HEADER_FIELDS:
        if attr in edited:
            continue
        value = document.get(key)
        default = None if attr.endswith("year") else ""
        setattr(reading_list, attr, value if value is not None else default)
    extra = dict(reading_list.extra or {})
    for key in _EXTRA_KEYS:
        if key in document:
            extra[key] = document[key]
        else:
            extra.pop(key, None)
    reading_list.extra = extra


def recombine(reading_list: ReadingList, matcher: ListMatcher | None = None) -> int:
    """Recompute a list from its sources, keeping hand edits; return its size."""
    matcher = matcher or ListMatcher()
    sources = list(
        ReadingListSource.objects.filter(reading_list=reading_list).order_by(
            "rank", "pk"
        )
    )
    entries = list(
        ReadingListEntry.objects.filter(reading_list=reading_list).order_by(
            "position", "pk"
        )
    )
    overlay = Overlay.of(entries)
    inputs = _inputs(reading_list, sources, entries)
    rows, combined = _combined_rows(inputs, locked=reading_list.order_locked)
    _apply_overlay(rows, overlay)
    _match_rows(rows, matcher)
    ordered = _with_manual(rows, overlay)
    new_entries = []
    for position, row in enumerate(ordered):
        if isinstance(row, ReadingListEntry):
            new_entries.append(_copy_manual(row, position))
        else:
            new_entries.append(_entry(reading_list, position, row))
    with transaction.atomic():
        ReadingListEntry.objects.filter(reading_list=reading_list).delete()
        ReadingListEntry.objects.bulk_create(new_entries, batch_size=_BATCH)
        _update_header(reading_list, combined)
        reading_list.save()
    return len(new_entries)


def rematch(reading_list: ReadingList, matcher: ListMatcher | None = None) -> int:
    """
    Match a list's missing entries again, without recombining.

    Run after an import adds comics, nightly, and on demand. An entry a
    person picked or hid is left alone. Returns how many entries found a
    comic.
    """
    matcher = matcher or ListMatcher()
    missing = list(
        ReadingListEntry.objects.filter(
            reading_list=reading_list, comic__isnull=True, ignored=False, manual=False
        ).order_by("position", "pk")
    )
    if not missing:
        return 0
    matches = matcher.match([entry.reference for entry in missing])
    found = []
    for entry, match in zip(missing, matches, strict=True):
        if match.comic_pk is None:
            continue
        entry.comic_id = match.comic_pk  # pyright: ignore[reportAttributeAccessIssue]
        entry.match_tier = match.tier
        entry.needs_review = match.needs_review
        found.append(entry)
    ReadingListEntry.objects.bulk_update(
        found, ("comic", "match_tier", "needs_review", "updated_at"), batch_size=_BATCH
    )
    if found:
        reading_list.save(update_fields=("updated_at",))
    return len(found)


def document_of(reading_list: ReadingList) -> dict[str, Any]:
    """Return a list as one JSON-safe comicbox document: header and entries."""
    entries = ReadingListEntry.objects.filter(
        reading_list=reading_list, ignored=False
    ).order_by("position", "pk")
    references = [entry.reference for entry in entries if entry.reference]
    document: dict[str, Any] = {"name": reading_list.name}
    for attr, key in _HEADER_FIELDS:
        if value := getattr(reading_list, attr):
            document[key] = value
    document.update(
        {key: value for key, value in (reading_list.extra or {}).items() if value}
    )
    document[ENTRIES_KEY] = references
    return document

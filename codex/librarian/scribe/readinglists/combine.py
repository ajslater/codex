"""
Recompute a reading list from its sources.

comicbox combines the sources' documents in rank order: the first ordered
source is the backbone whose order never moves, entries other sources add
go beside their neighbours, and every id any source knows is merged onto
each entry. Codex then maps the combined entries back to comics and keeps
what people did by hand:

- A row from the tags source is its comic: matched by definition.
- Hand edits are an overlay found again by the entry's identity (see
  :mod:`.overlay`): a hand-picked comic, an entry marked missing, a hidden
  entry and an accepted guess survive any recompute. They are saved in
  Codex only.
- Entries added by hand go back after the entry they followed. One whose
  comic is gone is matched again by its reference. One whose comic a
  source row holds folds into that row, which stays hand-added.
- A hand reorder locks the order: the current entries go first, so nothing
  moves, and entries new to the list are flagged for review.
- Every other entry goes through the matcher.

Removing a source recomputes the list without it, so a combination can be
undone.
"""

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import groupby
from operator import attrgetter, itemgetter
from typing import Any, Final

from comicbox.readinglists import combine
from django.db import transaction

from codex.choices.limits import MAX_NAME_LEN
from codex.librarian.scribe.readinglists.documents import (
    ENTRIES_KEY,
    tags_document,
    to_json,
)
from codex.librarian.scribe.readinglists.live import (
    COLLECTION_KIND,
    reconcile_includers,
    reconcile_list,
)
from codex.librarian.scribe.readinglists.matcher import ListMatcher
from codex.librarian.scribe.readinglists.overlay import (
    Edit,
    Overlay,
    reference_keys,
)
from codex.librarian.scribe.readinglists.references import issue_name
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
    # A folded hand-added entry is a source row too, so it keeps its place.
    kept = [
        entry.reference
        for entry in entries
        if entry.reference and source_pks.intersection(entry.source_ids or ())
    ]
    return {"name": reading_list.name, ENTRIES_KEY: kept}


def _inputs(
    reading_list: ReadingList,
    sources: Sequence[ReadingListSource],
    entries: Sequence[ReadingListEntry],
) -> list[_Input]:
    inputs: list[_Input] = []
    if reading_list.order_locked:
        # The current order goes first, unless it holds nothing a source
        # supplies: then there is no order to place new entries beside.
        source_pks = {source.pk for source in sources}
        current = _current_document(reading_list, entries, source_pks)
        if current[ENTRIES_KEY]:
            inputs.append(_Input(current))
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
    # A hand-added entry folded into this row.
    manual: bool = False


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


def _flagged(
    result, positions: Sequence[int], *, locked: bool
) -> tuple[set[int], set[int]]:
    """
    Return the combined positions a person should look at.

    First the joins that may be wrong: on a name alone, or with ids that
    disagree. Then, in a locked list, whatever the current order did not
    hold, which the combine placed beside its neighbours.
    """
    doubtful = set(result.name_joins)
    doubtful |= {conflict.entry for conflict in result.id_conflicts}
    placed: set[int] = set()
    if locked:
        placed = {
            index
            for index, origins in enumerate(result.provenance)
            if all(positions[origin.input_index] != 0 for origin in origins)
        }
    return doubtful, placed


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
    doubtful, placed = _flagged(result, positions, locked=locked)
    rows: list[_Row] = []
    for index, reference in enumerate(references):
        row = _row(reference, result.provenance[index], inputs, positions)
        # A comic's own arc tag settles which comic it is; a doubtful join
        # only matters where the matcher has to guess.
        guessed = row.tier != ReadingListMatchTier.TAGGED.value
        row.needs_review = index in placed or (guessed and index in doubtful)
        rows.append(row)
    return rows, combined


def _apply_pick(row: _Row, edit: Edit, live: set[int]) -> None:
    """Give a row the comic a person chose, or keep it missing as they said."""
    if row.tier == ReadingListMatchTier.TAGGED.value:
        return
    if edit.marked_missing:
        row.tier = ReadingListMatchTier.MARKED_MISSING
    elif edit.picked_pk is not None and edit.picked_pk in live:
        row.comic_pk = edit.picked_pk
        row.tier = ReadingListMatchTier.MANUAL


def _apply_overlay(rows: Sequence[_Row], overlay: Overlay) -> list[int | None]:
    """Put the hand edits on the rows; return each row's edit index."""
    picked_pks = overlay.picked_pks()
    live = set(Comic.objects.filter(pk__in=picked_pks).values_list("pk", flat=True))
    assigned = overlay.assign([reference_keys(row.reference) for row in rows])
    for row, index in zip(rows, assigned, strict=True):
        if index is not None:
            edit = overlay.edits[index]
            row.ignored = edit.ignored
            _apply_pick(row, edit, live)
    return assigned


def _keep_accepted(
    rows: Sequence[_Row], overlay: Overlay, assigned: Sequence[int | None]
) -> None:
    """Keep a guess a person let stand unflagged while it finds that comic."""
    for row, index in zip(rows, assigned, strict=True):
        if index is None or row.comic_pk is None:
            continue
        if overlay.edits[index].accepted_pk == row.comic_pk:
            row.needs_review = False


def _is_open(comic_pk: int | None, tier: str) -> bool:
    """Whether an entry wants a comic: none yet, and not marked missing."""
    return comic_pk is None and tier != ReadingListMatchTier.MARKED_MISSING.value


def _match_rows(rows: Sequence[_Row], matcher: ListMatcher) -> None:
    open_rows = [row for row in rows if _is_open(row.comic_pk, row.tier)]
    if not open_rows:
        return
    matches = matcher.match([row.reference for row in open_rows])
    for row, found in zip(open_rows, matches, strict=True):
        if found.comic_pk is None:
            continue
        row.comic_pk = found.comic_pk
        row.tier = found.tier
        row.needs_review = row.needs_review or found.needs_review


def _source_rows_by_comic(rows: Sequence[_Row]) -> dict[int, deque[int]]:
    """
    Map each comic to the positions of the shown rows a source gives it.

    The tags or the matcher gave the row its comic; a person's pick is a
    hand edit of its own and holds nothing a hand-added entry folds into.
    """
    held: defaultdict[int, deque[int]] = defaultdict(deque)
    for position, row in enumerate(rows):
        if (
            row.comic_pk is not None
            and not row.ignored
            and row.tier != ReadingListMatchTier.MANUAL.value
        ):
            held[row.comic_pk].append(position)
    return held


def _fold(row: _Row, entry: ReadingListEntry) -> None:
    """
    Make a source row the hand-added entry whose comic it holds.

    The row stays hand-added, so the comic outlives the source, and it
    keeps the entry's hidden flag and a review a person cleared.
    """
    row.manual = True
    row.ignored = entry.ignored
    row.needs_review = row.needs_review and entry.needs_review


def _with_manual(
    rows: Sequence[_Row], overlay: Overlay, assigned: Sequence[int | None]
) -> list[_Row | ReadingListEntry]:
    """
    Put each hand-added entry back after the entry it followed.

    A hand-added entry whose comic a shown source row now holds folds into
    that row, which takes its place for the hand-added entries after it. A
    list written into its comics' files then reads back once, not twice.
    """
    if not overlay.manual:
        return list(rows)
    row_of = {index: row for row, index in enumerate(assigned) if index is not None}
    held = _source_rows_by_comic(rows)
    after: dict[int | None, list[ReadingListEntry]] = {}
    for previous, run in groupby(overlay.manual, key=itemgetter(0)):
        target = None if previous is None else row_of.get(previous)
        for _, entry in run:
            comic_pk = entry.comic_id  # pyright: ignore[reportAttributeAccessIssue]
            if positions := held.get(comic_pk):
                target = positions.popleft()
                _fold(rows[target], entry)
                continue
            after.setdefault(target, []).append(entry)
    ordered: list[_Row | ReadingListEntry] = list(after.pop(None, []))
    for position, row in enumerate(rows):
        ordered.append(row)
        ordered.extend(after.pop(position, []))
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
        manual=row.manual,
        entry_type=row.entry_type[:32],
        source_ids=sorted(set(row.source_ids)),
    )


def _copy_manual(
    reading_list: ReadingList, entry: ReadingListEntry, position: int
) -> ReadingListEntry:
    """
    Return a hand-added entry again, at its new position.

    No source row took it, so no source supplies it, even one folded
    before.
    """
    return ReadingListEntry(
        reading_list=reading_list,
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


def _heal_manual(
    entries: Sequence[ReadingListEntry], matcher: ListMatcher
) -> list[ReadingListEntry]:
    """Find hand-added entries' comics again by reference; return the found."""
    lost = [
        entry
        for entry in entries
        if entry.manual and _is_open(entry.comic_id, entry.match_tier)  # pyright: ignore[reportAttributeAccessIssue]
    ]
    if not lost:
        return []
    healed = []
    for entry, found in zip(
        lost, matcher.match([entry.reference for entry in lost]), strict=True
    ):
        if found.comic_pk is not None:
            entry.comic_id = found.comic_pk  # pyright: ignore[reportAttributeAccessIssue]
            entry.match_tier = found.tier
            entry.needs_review = found.needs_review
            healed.append(entry)
    return healed


def _recombine_hand_made(
    reading_list: ReadingList,
    entries: Sequence[ReadingListEntry],
    matcher: ListMatcher,
) -> int:
    """
    Recompute a list no source feeds: a copy, or a list made by hand.

    There is nothing to combine, so only what was added by hand stays. The
    rows a last source supplied go with it, and a hand-added entry folded
    into one of them is supplied by none now. The order and the header
    stay as they are, and a hand-added entry whose comic went is matched
    again, in place.
    """
    own = ReadingListEntry.objects.filter(
        reading_list=reading_list, live_source__isnull=True
    )
    kept = [entry for entry in entries if entry.manual]
    with transaction.atomic():
        dropped, _ = own.filter(manual=False).delete()
        own.filter(manual=True).exclude(source_ids=[]).update(source_ids=[])
        healed = _heal_manual(kept, matcher)
        ReadingListEntry.objects.bulk_update(
            healed, ("comic", "match_tier", "needs_review"), batch_size=_BATCH
        )
        if dropped or healed:
            reading_list.save(update_fields=("updated_at",))
        reconcile_list(reading_list)
    return len(kept)


def _carried(overlay: Overlay) -> list[ReadingListEntry]:
    """
    Return the combined lists' hand-added entries, list by list, in order.

    A comic an earlier list holds comes once; a list's own repeat stays.
    """
    held: set[int] = set()
    carried: list[ReadingListEntry] = []
    entries = (entry for _, entry in overlay.manual)
    for _, run in groupby(entries, key=attrgetter("reading_list_id")):
        own = list(run)
        carried.extend(entry for entry in own if entry.comic_id not in held)  # pyright: ignore[reportAttributeAccessIssue]
        held.update(entry.comic_id for entry in own if entry.comic_id is not None)  # pyright: ignore[reportAttributeAccessIssue]
    return carried


def _combine_hand_made(
    reading_list: ReadingList, overlay: Overlay, matcher: ListMatcher
) -> int:
    """
    Combine lists no source feeds, such as two copies.

    The primary's hand-added entries come first, then each other list's;
    the rows of a source none of them has any more go, as for one list.
    """
    new_entries = [
        _copy_manual(reading_list, entry, position)
        for position, entry in enumerate(_carried(overlay))
    ]
    _heal_manual(new_entries, matcher)
    with transaction.atomic():
        ReadingListEntry.objects.filter(
            reading_list=reading_list, live_source__isnull=True
        ).delete()
        ReadingListEntry.objects.bulk_create(new_entries, batch_size=_BATCH)
        reading_list.save()
        reconcile_list(reading_list)
    return len(new_entries)


def recombine(
    reading_list: ReadingList,
    matcher: ListMatcher | None = None,
    overlay: Overlay | None = None,
) -> int:
    """
    Recompute a list from its sources, keeping hand edits; return its size.

    ``overlay`` defaults to the list's own edits; combining lists passes
    the edits of every list combined.
    """
    matcher = matcher or ListMatcher()
    # Collection items and their live entries are live.py's: a recompute
    # neither reads nor deletes them, and syncs them after.
    sources = list(
        ReadingListSource.objects.filter(reading_list=reading_list)
        .exclude(kind=COLLECTION_KIND)
        .order_by("rank", "pk")
    )
    entries = list(
        ReadingListEntry.objects.filter(
            reading_list=reading_list, live_source__isnull=True
        ).order_by("position", "pk")
    )
    if not sources:
        # Combining lists passes their edits; one list's are its entries.
        size = (
            _recombine_hand_made(reading_list, entries, matcher)
            if overlay is None
            else _combine_hand_made(reading_list, overlay, matcher)
        )
        reconcile_includers(reading_list)
        return size
    if overlay is None:
        overlay = Overlay.of(entries)
    inputs = _inputs(reading_list, sources, entries)
    rows, combined = _combined_rows(inputs, locked=reading_list.order_locked)
    assigned = _apply_overlay(rows, overlay)
    _match_rows(rows, matcher)
    _keep_accepted(rows, overlay, assigned)
    ordered = _with_manual(rows, overlay, assigned)
    new_entries = []
    for position, row in enumerate(ordered):
        if isinstance(row, ReadingListEntry):
            new_entries.append(_copy_manual(reading_list, row, position))
        else:
            new_entries.append(_entry(reading_list, position, row))
    _heal_manual(new_entries, matcher)
    with transaction.atomic():
        ReadingListEntry.objects.filter(
            reading_list=reading_list, live_source__isnull=True
        ).delete()
        ReadingListEntry.objects.bulk_create(new_entries, batch_size=_BATCH)
        _update_header(reading_list, combined)
        reading_list.save()
        reconcile_list(reading_list)
    reconcile_includers(reading_list)
    return len(new_entries)


def rematch(reading_list: ReadingList, matcher: ListMatcher | None = None) -> int:
    """
    Match a list's missing entries again, without recombining.

    Run after an import adds comics, nightly, and on demand. An entry a
    person hid or marked missing is left alone; any other entry without a
    comic, a hand-added one or a hand pick whose file went included, is
    matched by its reference. Returns how many entries found a comic.
    """
    matcher = matcher or ListMatcher()
    missing = list(
        ReadingListEntry.objects.filter(
            reading_list=reading_list,
            comic__isnull=True,
            ignored=False,
            live_source__isnull=True,
        )
        .exclude(match_tier=ReadingListMatchTier.MARKED_MISSING.value)
        .order_by("position", "pk")
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
    with transaction.atomic():
        ReadingListEntry.objects.bulk_update(
            found,
            ("comic", "match_tier", "needs_review", "updated_at"),
            batch_size=_BATCH,
        )
        if found:
            reading_list.save(update_fields=("updated_at",))
            # A found comic is held now: an item stops delivering it.
            reconcile_list(reading_list)
    if found:
        reconcile_includers(reading_list)
    return len(found)


def document_header(reading_list: ReadingList) -> dict[str, Any]:
    """Return a list's header as a JSON-safe comicbox document, no entries."""
    document: dict[str, Any] = {"name": reading_list.name}
    for attr, key in _HEADER_FIELDS:
        if value := getattr(reading_list, attr):
            document[key] = value
    extra = reading_list.extra or {}
    document.update({key: value for key in _EXTRA_KEYS if (value := extra.get(key))})
    return document


def document_of(reading_list: ReadingList) -> dict[str, Any]:
    """Return a list as one JSON-safe comicbox document: header and entries."""
    references = (
        ReadingListEntry.objects.filter(reading_list=reading_list, ignored=False)
        .order_by("position", "pk")
        .values_list("reference", flat=True)
    )
    document = document_header(reading_list)
    document[ENTRIES_KEY] = [reference for reference in references if reference]
    return document

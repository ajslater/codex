"""
Collection items: a whole publisher, series, folder or list kept current.

A collection item is a :class:`ReadingListSource` of kind ``collection``
bound to its row by ``(collection, target_id)``. Its ``ref`` and
``document`` carry an identity with no database id in it, the name chain
or path the user-data backup already encodes, so an item whose series
goes is left dangling, not deleted, and binds again when it returns.

Its comics are stored as live entries (``ReadingListEntry.live_source``)
so every reader of entries works unchanged. :func:`reconcile_list` alone
writes them: it diffs each item's comics against the rows and writes only
the difference. Its inputs are all derived, so a bug costs a re-sync,
never a person's edits. Live entries never go through comicbox.

- A comic appears in a list once. An item does not deliver a comic the
  list holds otherwise, by hand, from a source, or hidden; an earlier item
  wins over a later one.
- On a list with document or tags sources the items sit at the end. On a
  hand-made list each item's block sits where it was put and moves as a
  unit; ``position``, the number of the list's other entries before the
  block, places a block that has no comics.
- A list may hold a list, but never itself, a list that holds it, or, as a
  global list, a personal one. Lists sync targets first.
"""

import json
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha1
from itertools import batched
from math import inf
from types import MappingProxyType
from typing import Any, Final

from cachalot.api import cachalot_disabled
from django.db import connection, transaction
from django.db.models import F, Max, Model
from django.utils import timezone
from loguru import logger

from codex.collection import Collection
from codex.models import Comic
from codex.models.collections import Folder, Imprint, Publisher, Series, Volume
from codex.models.readinglist import (
    MAX_REF_LEN,
    ReadingList,
    ReadingListEntry,
    ReadingListMatchTier,
    ReadingListSource,
    ReadingListSourceKind,
)
from codex.user_data.identifiers import (
    decode_identifier,
    encode_identifier,
    identifier_for_browse_collection,
    resolve_browse_collection_pks,
)

COLLECTION_KIND: Final = ReadingListSourceKind.COLLECTION.value
# An item's full identity and its name for people, in its ``document``.
# ``ref`` holds the identity cut to the column, for display and lookups.
IDENTITY_KEY: Final = "identity"
LABEL_KEY: Final = "label"
# Above this many comics an item is synced by a librarian job.
LIVE_INLINE_LIMIT: Final = 2000

ITEM_MODELS: Final[MappingProxyType[str, type[Model]]] = MappingProxyType(
    {
        Collection.PUBLISHER.value: Publisher,
        Collection.IMPRINT.value: Imprint,
        Collection.SERIES.value: Series,
        Collection.VOLUME.value: Volume,
        Collection.FOLDER.value: Folder,
        Collection.ARC.value: ReadingList,
    }
)
_ARC: Final = Collection.ARC.value
_FOLDER: Final = Collection.FOLDER.value
_VOLUME: Final = Collection.VOLUME.value
# Comics whose own column holds the target's pk.
_COMIC_FIELD: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        Collection.PUBLISHER.value: "publisher_id",
        Collection.IMPRINT.value: "imprint_id",
        Collection.SERIES.value: "series_id",
        Collection.VOLUME.value: "volume_id",
    }
)
# Reading order within a block: series, volume, issue.
_COMIC_ORDER: Final = (
    "series__sort_name",
    "volume__name",
    "volume__number_to",
    "issue_number",
    "issue_suffix",
    "sort_name",
    "pk",
)
_RELATED: Final[MappingProxyType[str, tuple[str, ...]]] = MappingProxyType(
    {
        Collection.IMPRINT.value: ("publisher",),
        Collection.SERIES.value: ("publisher", "imprint"),
        Collection.VOLUME.value: ("publisher", "imprint", "series"),
    }
)
_BATCH: Final = 500
_ITEM_FIELDS: Final = ("target_id", "ref", "document", "revision", "position")


class ItemRefusedError(ValueError):
    """A collection item a list may not hold; the message says why."""


def items_q() -> dict[str, Any]:
    """Filter kwargs for collection items."""
    return {"kind": COLLECTION_KIND}


# ── Targets and identity ─────────────────────────────────────────────


def load_target(collection: str, target_id: int | None) -> Model | None:
    """Return an item's row, with what its identity reads, or None."""
    model = ITEM_MODELS.get(collection)
    if model is None or target_id is None:
        return None
    queryset = model.objects.filter(pk=target_id)
    if related := _RELATED.get(collection):
        queryset = queryset.select_related(*related)
    return queryset.first()


def _label(collection: str, target: Any) -> str:
    if collection == _VOLUME:
        number = Volume.to_str(target.name, target.number_to)
        return f"{target.series.name} {number}".strip()
    return str(target.name or getattr(target, "path", ""))


def item_identity(collection: str, target: Model) -> tuple[str, dict[str, str]]:
    """Return an item's ``ref`` and ``document``: its identity and label."""
    parts = identifier_for_browse_collection(collection, target)
    identity = encode_identifier(collection, parts)
    document = {IDENTITY_KEY: identity, LABEL_KEY: _label(collection, target)}
    return identity[:MAX_REF_LEN], document


def _candidates(item: ReadingListSource) -> tuple[int, ...]:
    """Rows a dangling item's identity names, lowest pk first."""
    identity = (item.document or {}).get(IDENTITY_KEY) or item.ref
    try:
        collection, parts = decode_identifier(identity)
    except (ValueError, TypeError):
        return ()
    if collection != item.collection:
        return ()
    return resolve_browse_collection_pks(collection, parts, ITEM_MODELS[collection])


# ── Guards ───────────────────────────────────────────────────────────


def held_lists(list_pks: Iterable[int]) -> set[int]:
    """Return every list the given lists hold, directly or through others."""
    seen: set[int] = set()
    frontier = set(list_pks)
    while frontier:
        targets = set(
            ReadingListSource.objects.filter(
                **items_q(),
                collection=_ARC,
                reading_list_id__in=frontier,
                target_id__isnull=False,
            ).values_list("target_id", flat=True)
        )
        frontier = targets - seen
        seen |= frontier
    return seen


def includers(list_pks: Iterable[int]) -> set[int]:
    """Return every list that holds the given lists, directly or through others."""
    seen: set[int] = set()
    frontier = set(list_pks)
    while frontier:
        holders = set(
            ReadingListSource.objects.filter(
                **items_q(), collection=_ARC, target_id__in=frontier
            ).values_list("reading_list_id", flat=True)
        )
        frontier = holders - seen
        seen |= frontier
    return seen


def list_refusal(reading_list: ReadingList, target: ReadingList) -> str:
    """Say why a list may not hold another list, or return ""."""
    if target.pk == reading_list.pk:
        return "A list cannot hold itself."
    owner = reading_list.user_id  # pyright: ignore[reportAttributeAccessIssue]
    target_owner = target.user_id  # pyright: ignore[reportAttributeAccessIssue]
    if target_owner is not None:
        if owner is None:
            return "A global list cannot hold a personal list."
        if owner != target_owner:
            return "That list belongs to someone else."
    if reading_list.pk in held_lists((target.pk,)):
        return "That list already holds this one."
    return ""


def owner_refusal(reading_list: ReadingList, owner_id: int | None) -> str:
    """Say why a list may not change owner, or return ""."""
    if owner_id is None:
        held = ReadingListSource.objects.filter(
            reading_list=reading_list,
            **items_q(),
            collection=_ARC,
            target_id__isnull=False,
        ).values_list("target_id", flat=True)
        if ReadingList.objects.filter(pk__in=list(held), user__isnull=False).exists():
            return "It holds personal lists, which a global list cannot."
        return ""
    holders = ReadingListSource.objects.filter(
        **items_q(), collection=_ARC, target_id=reading_list.pk
    ).values_list("reading_list_id", flat=True)
    others = ReadingList.objects.filter(pk__in=list(holders)).exclude(user_id=owner_id)
    if others.exists():
        return "Other lists hold it, so it must stay where they can see it."
    return ""


def _next_rank(reading_list: ReadingList) -> int:
    top = ReadingListSource.objects.filter(reading_list=reading_list).aggregate(
        top=Max("rank")
    )["top"]
    return 0 if top is None else top + 1


def add_item(
    reading_list: ReadingList,
    collection: str,
    target_id: int,
    *,
    position: int | None = None,
) -> ReadingListSource:
    """
    Put a whole collection into a list; the caller syncs the list.

    ``position`` places the block among a hand-made list's other entries.
    Raises :class:`ItemRefusedError` for an unknown or missing target, one
    the list already holds, or a list the list may not hold.
    """
    target = load_target(collection, target_id)
    if target is None:
        reason = "That collection does not exist."
        raise ItemRefusedError(reason)
    if isinstance(target, ReadingList) and (
        reason := list_refusal(reading_list, target)
    ):
        raise ItemRefusedError(reason)
    held = ReadingListSource.objects.filter(
        reading_list=reading_list,
        **items_q(),
        collection=collection,
        target_id=target_id,
    )
    if held.exists():
        reason = "The list already holds that."
        raise ItemRefusedError(reason)
    ref, document = item_identity(collection, target)
    return ReadingListSource.objects.create(
        reading_list=reading_list,
        kind=COLLECTION_KIND,
        collection=collection,
        target_id=target_id,
        ref=ref,
        document=document,
        rank=_next_rank(reading_list),
        position=position,
    )


# ── Members ──────────────────────────────────────────────────────────


def member_comics(collection: str, target_id: int | None) -> list[int]:
    """
    Return a collection's comics in reading order.

    A comic pending delete keeps its row and links, so it stays a member:
    reads hide it, the list keeps its place.
    """
    if target_id is None:
        return []
    with cachalot_disabled():
        if collection == _ARC:
            rows = (
                ReadingListEntry.objects.filter(
                    reading_list_id=target_id, ignored=False, comic__isnull=False
                )
                .order_by("position", "pk")
                .values_list("comic_id", flat=True)
            )
            return list(dict.fromkeys(rows))
        if collection == _FOLDER:
            comics = Comic.objects.filter(folders=target_id).order_by("path", "pk")
        else:
            field_name = _COMIC_FIELD[collection]
            comics = Comic.objects.filter(**{field_name: target_id}).order_by(
                *_COMIC_ORDER
            )
        return list(comics.values_list("pk", flat=True))


def _digest(comics: Sequence[int]) -> str:
    return sha1(json.dumps(list(comics)).encode(), usedforsecurity=False).hexdigest()


def is_large(collection: str, target_id: int) -> bool:
    """Whether a collection is big enough to sync in a librarian job."""
    with cachalot_disabled():
        if collection == _ARC:
            count = ReadingListEntry.objects.filter(reading_list_id=target_id).count()
        elif collection == _FOLDER:
            count = Comic.objects.filter(folders=target_id).count()
        else:
            count = Comic.objects.filter(
                **{_COMIC_FIELD[collection]: target_id}
            ).count()
    return count > LIVE_INLINE_LIMIT


# ── Binding ──────────────────────────────────────────────────────────


def _refresh(item: ReadingListSource, target: Model) -> bool:
    """Keep a bound item's identity current: a folder moves in place."""
    ref, document = item_identity(item.collection, target)
    current: Any = item.document
    if ref == item.ref and document == current:
        return False
    item.ref = ref
    item.document = document  # pyright: ignore[reportAttributeAccessIssue]
    return True


def _rebind(
    reading_list: ReadingList, item: ReadingListSource, taken: set[tuple[str, int]]
) -> bool:
    """Bind a dangling item to the first free row its identity names."""
    for target_id in _candidates(item):
        if (item.collection, target_id) in taken:
            continue
        target = load_target(item.collection, target_id)
        if target is None:
            continue
        if isinstance(target, ReadingList) and list_refusal(reading_list, target):
            continue
        item.target_id = target_id
        _refresh(item, target)
        taken.add((item.collection, target_id))
        return True
    return False


def _bind(reading_list: ReadingList, items: Sequence[ReadingListSource]) -> bool:
    """Dangle items whose row went, bind dangling ones, refresh the rest."""
    changed = False
    for item in items:
        if item.target_id is None:
            continue
        target = load_target(item.collection, item.target_id)
        if target is None:
            item.target_id = None
            changed = True
        else:
            changed |= _refresh(item, target)
    taken = {(item.collection, item.target_id) for item in items if item.target_id}
    for item in items:
        if item.target_id is None:
            changed |= _rebind(reading_list, item, taken)
    return changed


# ── Placing blocks ───────────────────────────────────────────────────


@dataclass(slots=True)
class _Block:
    item: ReadingListSource
    anchor: int
    first: float = inf
    comics: list[int] = field(default_factory=list)


def _blocks(
    entries: Sequence[ReadingListEntry],
    items: Sequence[ReadingListSource],
    *,
    sourced: bool,
) -> list[_Block]:
    """Place each item's block among the list's other entries."""
    others = 0
    first: dict[int, tuple[int, int]] = {}
    for entry in entries:
        source_pk = entry.live_source_id  # pyright: ignore[reportAttributeAccessIssue]
        if source_pk is None:
            others += 1
        elif source_pk not in first:
            first[source_pk] = (others, entry.position)
    blocks = []
    for item in items:
        anchor, position = first.get(item.pk, (others, inf))
        if sourced:
            anchor = others
        elif item.pk not in first and item.position is not None:
            anchor = min(item.position, others)
        blocks.append(_Block(item, anchor, position))
    blocks.sort(
        key=lambda block: (block.anchor, block.first, block.item.rank, block.item.pk)
    )
    return blocks


def _fill(
    blocks: Sequence[_Block], entries: Sequence[ReadingListEntry]
) -> dict[int, list[int]]:
    """Give each block its comics, once per list; return each item's members."""
    delivered = {
        entry.comic_id  # pyright: ignore[reportAttributeAccessIssue]
        for entry in entries
        if entry.live_source_id is None and entry.comic_id is not None  # pyright: ignore[reportAttributeAccessIssue]
    }
    members = {}
    for block in blocks:
        comics = member_comics(block.item.collection, block.item.target_id)
        members[block.item.pk] = comics
        block.comics = [pk for pk in comics if pk not in delivered]
        delivered.update(block.comics)
    return members


@dataclass(slots=True)
class _Plan:
    sequence: list[ReadingListEntry]
    new: list[ReadingListEntry]
    stale: list[int]


def _existing_live(
    entries: Sequence[ReadingListEntry],
) -> tuple[dict[tuple[int, int | None], ReadingListEntry], list[int]]:
    """Index the live entries by (item, comic); a repeat is stale."""
    existing: dict[tuple[int, int | None], ReadingListEntry] = {}
    stale: list[int] = []
    for entry in entries:
        source_pk = entry.live_source_id  # pyright: ignore[reportAttributeAccessIssue]
        if source_pk is None:
            continue
        key = (source_pk, entry.comic_id)  # pyright: ignore[reportAttributeAccessIssue]
        if key in existing:
            stale.append(entry.pk)
        else:
            existing[key] = entry
    return existing, stale


def _block_rows(
    reading_list: ReadingList,
    block: _Block,
    existing: dict[tuple[int, int | None], ReadingListEntry],
    new: list[ReadingListEntry],
) -> list[ReadingListEntry]:
    """Return a block's rows in order, made new for comics without one."""
    rows = []
    for comic_pk in block.comics:
        row = existing.pop((block.item.pk, comic_pk), None)
        if row is None:
            row = ReadingListEntry(
                reading_list=reading_list,
                comic_id=comic_pk,
                live_source=block.item,
                match_tier=ReadingListMatchTier.COLLECTION,
            )
            new.append(row)
        rows.append(row)
    return rows


def _plan(
    reading_list: ReadingList,
    entries: Sequence[ReadingListEntry],
    blocks: Sequence[_Block],
) -> _Plan:
    """Lay out the list: other entries in order, each block at its anchor."""
    others = [entry for entry in entries if entry.live_source_id is None]  # pyright: ignore[reportAttributeAccessIssue]
    existing, stale = _existing_live(entries)
    at: dict[int, list[_Block]] = defaultdict(list)
    for block in blocks:
        at[block.anchor].append(block)
    sequence: list[ReadingListEntry] = []
    new: list[ReadingListEntry] = []
    for index in range(len(others) + 1):
        for block in at.get(index, ()):
            sequence.extend(_block_rows(reading_list, block, existing, new))
        sequence.extend(others[index : index + 1])
    stale.extend(entry.pk for entry in existing.values())
    for position, row in enumerate(sequence):
        if row.pk is None:
            row.position = position
    return _Plan(sequence, new, stale)


# ── Writing ──────────────────────────────────────────────────────────


def renumber(pks: Sequence[int]) -> int:
    """
    Set entries' positions 0..n-1 in the given order, in one statement.

    Writes only the rows whose position changes, and returns how many.
    cachalot invalidates the table: the SQL names it literally.
    """
    if not pks:
        return 0
    table = ReadingListEntry._meta.db_table
    sql = (
        f"UPDATE {table} SET position = j.key "  # noqa: S608
        "FROM json_each(%s) AS j "
        f"WHERE {table}.id = j.value AND {table}.position <> j.key"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [json.dumps(list(pks))])
        return cursor.rowcount


def _write(plan: _Plan) -> bool:
    for pks in batched(plan.stale, _BATCH):
        ReadingListEntry.objects.filter(pk__in=pks).delete()
    ReadingListEntry.objects.bulk_create(plan.new, batch_size=_BATCH)
    moved = renumber([row.pk for row in plan.sequence])
    return bool(plan.stale or plan.new or moved)


def _save_items(
    blocks: Sequence[_Block], members: Mapping[int, list[int]], *, sourced: bool
) -> None:
    items = []
    for block in blocks:
        item = block.item
        item.revision = _digest(members.get(item.pk, ()))
        item.position = None if sourced else block.anchor
        items.append(item)
    ReadingListSource.objects.bulk_update(items, _ITEM_FIELDS, batch_size=_BATCH)


def lock_list(reading_list: ReadingList) -> None:
    """
    Take the write lock first, before reading what to write.

    Call it first in a transaction that reads and then writes. SQLite
    starts one deferred, and under WAL a transaction that read before
    another connection committed cannot write: SQLITE_BUSY_SNAPSHOT, at
    once, whatever the busy timeout.
    """
    ReadingList.objects.filter(pk=reading_list.pk).update(updated_at=F("updated_at"))


def _touch(reading_list: ReadingList) -> None:
    now = timezone.now()
    ReadingList.objects.filter(pk=reading_list.pk).update(updated_at=now)
    reading_list.updated_at = now


def _close_gaps(reading_list: ReadingList) -> bool:
    """Renumber a list's entries 0..n-1; return whether any moved."""
    pks = (
        ReadingListEntry.objects.filter(reading_list=reading_list)
        .order_by("position", "pk")
        .values_list("pk", flat=True)
    )
    if not renumber(list(pks)):
        return False
    _touch(reading_list)
    return True


def reconcile_list(reading_list: ReadingList) -> bool:
    """
    Bring a list's live entries in line with its items; return if it changed.

    A full diff of every item, in order, against the rows: everything that
    changes a list calls it, so the comics a list holds otherwise are
    re-read each time.
    """
    with transaction.atomic():
        lock_list(reading_list)
        items = list(
            ReadingListSource.objects.filter(
                reading_list=reading_list, **items_q()
            ).order_by("rank", "pk")
        )
        live_rows = ReadingListEntry.objects.filter(
            reading_list=reading_list, live_source__isnull=False
        )
        if not items and not live_rows.exists():
            # Its last item may just have gone, with the rows it brought.
            return _close_gaps(reading_list)
        rebound = _bind(reading_list, items)
        sourced = (
            ReadingListSource.objects.filter(reading_list=reading_list)
            .exclude(**items_q())
            .exists()
        )
        entries = list(
            ReadingListEntry.objects.filter(reading_list=reading_list)
            .order_by("position", "pk")
            .only("pk", "position", "comic_id", "live_source_id")
        )
        blocks = _blocks(entries, items, sourced=sourced)
        members = _fill(blocks, entries)
        changed = _write(_plan(reading_list, entries, blocks)) or rebound
        _save_items(blocks, members, sourced=sourced)
        if changed:
            _touch(reading_list)
    return changed


# ── Syncing many lists ───────────────────────────────────────────────


def _is_stale(reading_list: ReadingList) -> bool:
    """Whether any item's row or comics changed since it last synced."""
    items = ReadingListSource.objects.filter(reading_list=reading_list, **items_q())
    for item in items:
        if item.target_id is None:
            if _candidates(item):
                return True
            continue
        if load_target(item.collection, item.target_id) is None:
            return True
        if _digest(member_comics(item.collection, item.target_id)) != item.revision:
            return True
    return False


def _waits(list_pks: set[int]) -> dict[int, set[int]]:
    """Map each list to the lists it holds among ``list_pks``."""
    waits: dict[int, set[int]] = {pk: set() for pk in list_pks}
    edges = ReadingListSource.objects.filter(
        **items_q(),
        collection=_ARC,
        reading_list_id__in=list_pks,
        target_id__in=list_pks,
    ).values_list("reading_list_id", "target_id")
    for includer, target in edges:
        if includer != target:
            waits[includer].add(target)
    return waits


def _targets_first(list_pks: set[int]) -> tuple[list[int], set[int]]:
    """Order lists so a list syncs after the lists it holds; return cycles."""
    waits = _waits(list_pks)
    holders: dict[int, set[int]] = defaultdict(set)
    for includer, targets in waits.items():
        for target in targets:
            holders[target].add(includer)
    ready = deque(sorted(pk for pk, targets in waits.items() if not targets))
    order: list[int] = []
    while ready:
        pk = ready.popleft()
        order.append(pk)
        for holder in sorted(holders.get(pk, ())):
            waits[holder].discard(pk)
            if not waits[holder]:
                ready.append(holder)
    return order, list_pks - set(order)


def _lists_with_items(list_pks: Iterable[int] | None) -> set[int]:
    lists = ReadingListSource.objects.filter(**items_q())
    if list_pks is not None:
        wanted = set(list_pks)
        wanted |= includers(wanted)
        lists = lists.filter(reading_list_id__in=wanted)
    return set(lists.values_list("reading_list_id", flat=True))


def sync_live(*, force: bool = False, list_pks: Iterable[int] | None = None) -> int:
    """
    Sync lists with collection items, targets first; return how many changed.

    Without ``force`` a list syncs only when an item's row or comics
    changed, the import-time trigger. ``force`` reconciles every one: the
    nightly run. ``list_pks`` narrows the run to those lists and the lists
    that hold them. Lists that hold each other in a cycle are left alone.
    """
    order, cyclic = _targets_first(_lists_with_items(list_pks))
    if cyclic:
        logger.warning(
            f"Reading lists hold each other in a cycle; not synced: {sorted(cyclic)}"
        )
    dirty: set[int] = set()
    changed = 0
    for pk in order:
        reading_list = ReadingList.objects.filter(pk=pk).first()
        if reading_list is None:
            continue
        if not (force or pk in dirty or _is_stale(reading_list)):
            continue
        if reconcile_list(reading_list):
            changed += 1
            dirty |= includers((pk,))
    return changed


def reconcile_includers(reading_list: ReadingList) -> int:
    """Sync every list that holds this one, after it changed."""
    if holders := includers((reading_list.pk,)):
        return sync_live(force=True, list_pks=holders)
    return 0


def sweep_live() -> int:
    """
    Drop live entries whose comic is gone; return how many.

    A deleted comic leaves its entries comicless. A live entry has no
    reference to find it again by, so it goes, and its list renumbers.
    """
    rows = ReadingListEntry.objects.filter(
        live_source__isnull=False, comic__isnull=True
    )
    list_pks = set(rows.values_list("reading_list_id", flat=True))
    count, _ = rows.delete()
    for reading_list in ReadingList.objects.filter(pk__in=list_pks):
        reconcile_list(reading_list)
    return count

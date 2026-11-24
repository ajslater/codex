"""
Reading list operations: what the admin screen and the librarian jobs do.

Every change to a list's sources ends in a recombine, so the list always
reads as its sources combined plus the hand edits.
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from comicbox.readinglists import (
    LIST_TYPE_KEY,
    NAME_KEY,
    ORDERED_KEY,
    SOURCE_CURATOR_KEY,
    SOURCE_CURATOR_URL_KEY,
    SOURCE_KEY_KEY,
    SOURCE_KIND_KEY,
    SOURCE_REVISION_KEY,
    SOURCES_KEY,
    Verdict,
    compare,
    normalize_series,
)
from django.db import transaction
from django.db.models import Max, Q
from django.utils.timezone import now

from codex.choices.limits import MAX_NAME_LEN
from codex.collection import Collection
from codex.librarian.scribe.readinglists.combine import document_of, recombine
from codex.librarian.scribe.readinglists.documents import (
    COMICBOX_KINDS,
    ENTRIES_KEY,
    from_json,
)
from codex.librarian.scribe.readinglists.live import (
    COLLECTION_KIND,
    item_identity,
    list_refusal,
    reconcile_list,
)
from codex.librarian.scribe.readinglists.matcher import ListMatcher
from codex.librarian.scribe.readinglists.overlay import Overlay
from codex.librarian.scribe.readinglists.sync import is_disposable
from codex.models.readinglist import (
    MAX_REF_LEN,
    MAX_REVISION_LEN,
    ReadingList,
    ReadingListEntry,
    ReadingListMatchTier,
    ReadingListSource,
    ReadingListSourceKind,
)

# A list's own name groups: a bracketed publisher, a parenthesized curator.
_NAME_NOISE_RE: Final = re.compile(r"\[[^\]]*\]|\([^)]*\)")
# Sources a refresh can fetch again.
REMOTE_KINDS: Final = frozenset(
    {
        ReadingListSourceKind.URL,
        ReadingListSourceKind.CATALOG,
        ReadingListSourceKind.METRON_LIST,
        ReadingListSourceKind.METRON_ARC,
        ReadingListSourceKind.COMICVINE_ARC,
    }
)


def name_key(name: str) -> str:
    """Return a name to group lists of one event by: no brackets, normalized."""
    return normalize_series(_NAME_NOISE_RE.sub(" ", name or ""))


def _fetched_source(document: Mapping[str, Any], kind: str) -> dict[str, Any]:
    """Return the document's own record of where it came from, if any."""
    wanted = COMICBOX_KINDS.get(kind)
    sources = [source for source in document.get(SOURCES_KEY) or () if source]
    for source in sources:
        if wanted and source.get(SOURCE_KIND_KEY) == wanted:
            return source
    return sources[0] if sources else {}


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Where a document came from, as the admin chose to import it."""

    kind: str
    ref: str
    revision: str = ""
    attribution_source: str = ""
    attribution_url: str = ""

    @classmethod
    def of(cls, document: Mapping[str, Any], kind: str, ref: str) -> "SourceSpec":
        """Read the revision and curator off a fetched document."""
        fetched = _fetched_source(document, kind)
        key = (
            fetched.get(SOURCE_KEY_KEY)
            if kind == ReadingListSourceKind.CATALOG.value
            else None
        )
        return cls(
            kind=kind,
            ref=str(key or ref)[:MAX_REF_LEN],
            revision=str(fetched.get(SOURCE_REVISION_KEY) or "")[:MAX_REVISION_LEN],
            attribution_source=str(fetched.get(SOURCE_CURATOR_KEY) or "")[
                :MAX_NAME_LEN
            ],
            attribution_url=str(fetched.get(SOURCE_CURATOR_URL_KEY) or "")[
                :MAX_REF_LEN
            ],
        )


def _next_rank(reading_list: ReadingList) -> int:
    top = ReadingListSource.objects.filter(reading_list=reading_list).aggregate(
        top=Max("rank")
    )["top"]
    return 0 if top is None else top + 1


def unique_name(name: str, user) -> str:
    """
    Personal list names are unique per owner: number a repeat.

    The name is cut so its `` (N)`` fits in ``MAX_NAME_LEN``: the field cuts
    every lookup there, so a suffix past it would never be seen.
    """
    if user is None:
        return name
    candidate, number = name, 2
    while ReadingList.objects.filter(user=user, name=candidate).exists():
        suffix = f" ({number})"
        candidate = f"{name[: MAX_NAME_LEN - len(suffix)]}{suffix}"
        number += 1
    return candidate


def copy_list(
    original: ReadingList,
    *,
    user,
    name: str,
    entries_q: Q | None = None,
    items_q: Q | None = None,
) -> ReadingList:
    """
    Copy a list's shown entries into a new list, as entries added by hand.

    ``user`` owns the copy; None makes it global. ``entries_q`` and
    ``items_q`` narrow the entries and the collection items to what the
    copier sees. The copy's order is locked, since it has no sources to
    follow. The header it copies counts as edited, so a source added to the
    copy later does not overwrite it.
    """
    header = {
        "description": original.description,
        "list_type": original.list_type,
        "start_year": original.start_year,
        "end_year": original.end_year,
    }
    edited = sorted(key for key, value in header.items() if value not in (None, ""))
    with transaction.atomic():
        copy = ReadingList.objects.create(
            name=unique_name(name[:MAX_NAME_LEN], user),
            user=user,
            **header,
            edited_fields=edited,
            order_locked=True,
        )
        entries = (
            ReadingListEntry.objects.filter(
                reading_list=original, ignored=False, live_source__isnull=True
            )
            .filter(entries_q or Q())
            .order_by("position", "pk")
        )
        ReadingListEntry.objects.bulk_create(
            ReadingListEntry(
                reading_list=copy,
                position=position,
                comic_id=entry.comic_id,  # pyright: ignore[reportAttributeAccessIssue]
                reference=entry.reference,
                series_name=entry.series_name,
                issue=entry.issue,
                year=entry.year,
                entry_type=entry.entry_type,
                match_tier=ReadingListMatchTier.MANUAL
                if entry.comic_id  # pyright: ignore[reportAttributeAccessIssue]
                else ReadingListMatchTier.NONE,
                manual=True,
            )
            for position, entry in enumerate(entries)
        )
        _copy_items(original, copy, items_q or Q())
        reconcile_list(copy)
    return copy


def _may_hold(reading_list: ReadingList, item: ReadingListSource) -> bool:
    """Whether a list may hold an item's list; anything else it may."""
    if item.collection != Collection.ARC.value or item.target_id is None:
        return True
    target = ReadingList.objects.filter(pk=item.target_id).first()
    return target is None or not list_refusal(reading_list, target)


def _copy_items(original: ReadingList, copy: ReadingList, items_q: Q) -> None:
    """Copy a list's collection items into its copy, where they stay live."""
    items = (
        ReadingListSource.objects.filter(reading_list=original, kind=COLLECTION_KIND)
        .filter(items_q)
        .order_by("rank", "pk")
    )
    copies = [
        ReadingListSource(
            reading_list=copy,
            kind=COLLECTION_KIND,
            collection=item.collection,
            target_id=item.target_id,
            ref=item.ref,
            document=item.document,
            rank=rank,
            position=item.position,
        )
        for rank, item in enumerate(i for i in items if _may_hold(copy, i))
    ]
    ReadingListSource.objects.bulk_create(copies)


def import_document(
    document: Mapping[str, Any],
    spec: SourceSpec,
    *,
    into: ReadingList | None = None,
    user=None,
    name: str = "",
    matcher: ListMatcher | None = None,
) -> ReadingList:
    """
    Store a fetched or uploaded list as a source and recompute its list.

    ``into`` adds the source to an existing list, which is how two lists
    combine; otherwise a new list is made, global unless ``user`` owns it.
    A source already on the list is refreshed instead of added twice.
    """
    with transaction.atomic():
        if into is None:
            list_name = (name or document.get(NAME_KEY) or spec.ref)[:MAX_NAME_LEN]
            into = ReadingList.objects.create(
                name=unique_name(list_name, user),
                user=user,
                list_type=str(document.get(LIST_TYPE_KEY) or "")[:64],
            )
        source = ReadingListSource.objects.filter(
            reading_list=into, kind=spec.kind, ref=spec.ref
        ).first()
        if source is None:
            source = ReadingListSource(
                reading_list=into, kind=spec.kind, ref=spec.ref, rank=_next_rank(into)
            )
        source.document = dict(document)  # pyright: ignore[reportAttributeAccessIssue]
        source.revision = spec.revision
        source.attribution_source = spec.attribution_source
        source.attribution_url = spec.attribution_url
        source.ordered = document.get(ORDERED_KEY) is not False
        source.fetched_at = now()
        source.save()
        recombine(into, matcher)
    return into


def refresh_source(
    source: ReadingListSource,
    document: Mapping[str, Any] | None,
    matcher: ListMatcher | None = None,
) -> bool:
    """
    Replace a source's document with a fresh fetch and recompute its list.

    ``None`` means the remote said it is unchanged. A document with no
    issues never replaces a stored one: a remote that answers with an
    empty list has more likely failed than emptied it. Returns whether the
    list changed.
    """
    source.fetched_at = now()
    if not document or not document.get(ENTRIES_KEY):
        source.save(update_fields=("fetched_at", "updated_at"))
        return False
    spec = SourceSpec.of(document, source.kind, source.ref)
    if source.revision and spec.revision == source.revision:
        source.save(update_fields=("fetched_at", "updated_at"))
        return False
    source.document = dict(document)  # pyright: ignore[reportAttributeAccessIssue]
    source.revision = spec.revision
    source.ref = spec.ref
    source.attribution_source = spec.attribution_source or source.attribution_source
    source.attribution_url = spec.attribution_url or source.attribution_url
    source.ordered = document.get(ORDERED_KEY) is not False
    source.save()
    recombine(source.reading_list, matcher)
    return True


def remove_source(source: ReadingListSource) -> bool:
    """Remove a source and recompute; return whether its list survived."""
    reading_list = source.reading_list
    with transaction.atomic():
        source.delete()
        if is_disposable(reading_list, source.kind):
            reading_list.delete()
            return False
        recombine(reading_list)
    return True


def rank_sources(reading_list: ReadingList, source_pks: Iterable[int]) -> None:
    """Reorder a list's sources; the first is the primary. Then recompute."""
    order = {pk: rank for rank, pk in enumerate(source_pks)}
    # Collection items keep their own order: they are not combined.
    sources = list(
        ReadingListSource.objects.filter(reading_list=reading_list).exclude(
            kind=COLLECTION_KIND
        )
    )
    tail = len(order)
    for source in sources:
        source.rank = order.get(source.pk, tail)
    ReadingListSource.objects.bulk_update(sources, ("rank",))
    recombine(reading_list)


def _overlay_of(reading_list: ReadingList) -> Overlay:
    return Overlay.of(
        ReadingListEntry.objects.filter(
            reading_list=reading_list, live_source__isnull=True
        ).order_by("position", "pk")
    )


def _move_source(
    source: ReadingListSource, primary: ReadingList, absorbed: set[int], rank: int
) -> bool:
    """Move another list's source into the primary; return whether it moved."""
    if source.kind == COLLECTION_KIND:
        held = source.target_id is not None and ReadingListSource.objects.filter(
            reading_list=primary,
            kind=COLLECTION_KIND,
            collection=source.collection,
            target_id=source.target_id,
        )
        if (held and held.exists()) or source.target_id in absorbed:
            return False
        if not _may_hold(primary, source):
            return False
        # Its comics were the absorbed list's rows: sync them afresh.
        source.revision = ""
    elif ReadingListSource.objects.filter(
        reading_list=primary, kind=source.kind, ref=source.ref
    ).exists():
        return False
    source.reading_list = primary
    source.rank = rank
    source.save(update_fields=("reading_list", "rank", "revision", "updated_at"))
    return True


def _repoint_holders(primary: ReadingList, absorbed: set[int]) -> None:
    """Point the lists that held an absorbed list at the primary, if allowed."""
    ref, document = item_identity(Collection.ARC.value, primary)
    holders = ReadingListSource.objects.filter(
        kind=COLLECTION_KIND, collection=Collection.ARC.value, target_id__in=absorbed
    ).select_related("reading_list")
    for item in holders:
        holder = item.reading_list
        if holder.pk == primary.pk or list_refusal(holder, primary):
            continue
        if ReadingListSource.objects.filter(
            reading_list=holder,
            kind=COLLECTION_KIND,
            collection=Collection.ARC.value,
            target_id=primary.pk,
        ).exists():
            continue
        item.target_id = primary.pk
        item.ref = ref
        item.document = document  # pyright: ignore[reportAttributeAccessIssue]
        item.revision = ""
        item.save(update_fields=("target_id", "ref", "document", "revision"))


def combine_lists(primary: ReadingList, others: Iterable[ReadingList]) -> ReadingList:
    """
    Combine lists into ``primary``, whose order wins.

    The others' sources join the primary's after its own, and the others
    are deleted. Every list's hand edits come along: picks, hidden entries,
    entries marked missing and hand-added entries, the primary's winning
    where two lists edited one issue. Their collection items move too,
    except one that would make the primary hold itself, and lists that held
    an absorbed list hold the primary. Removing a source later undoes the
    combination.
    """
    others = [other for other in others if other.pk != primary.pk]
    absorbed = {other.pk for other in others}
    with transaction.atomic():
        # An item of the primary holding an absorbed list would hold itself.
        ReadingListSource.objects.filter(
            reading_list=primary,
            kind=COLLECTION_KIND,
            collection=Collection.ARC.value,
            target_id__in=absorbed,
        ).delete()
        rank = _next_rank(primary)
        overlay = _overlay_of(primary)
        for other in others:
            overlay.absorb(_overlay_of(other))
            for source in ReadingListSource.objects.filter(reading_list=other).order_by(
                "rank", "pk"
            ):
                if _move_source(source, primary, absorbed, rank):
                    rank += 1
        _repoint_holders(primary, absorbed)
        for other in others:
            other.delete()
        recombine(primary, overlay=overlay)
    return primary


def compare_documents(a: Mapping[str, Any], b: Mapping[str, Any]):
    """Compare two comicbox documents, model-loaded."""
    return compare(from_json(a) if a else {}, from_json(b) if b else {})


@dataclass(frozen=True, slots=True)
class Suggestion:
    """Two lists that look like one reading order, or two takes on one."""

    pk: int
    other_pk: int
    verdict: str
    combine: bool
    overlap: float


def _suggests_combining(verdict: Verdict, *, either_is_tags: bool) -> bool:
    """Combine the same order, or a tags list inside a curated one."""
    return verdict == Verdict.SAME or (verdict == Verdict.SUBSET and either_is_tags)


def _is_tags_only(reading_list: ReadingList) -> bool:
    kinds = set(
        ReadingListSource.objects.filter(reading_list=reading_list).values_list(
            "kind", flat=True
        )
    )
    return kinds == {ReadingListSourceKind.TAGS.value}


def suggest_for(document: Mapping[str, Any], *, exclude=()) -> list[Suggestion]:
    """Suggest what to do with a new document against global lists of its name."""
    key = name_key(str(document.get(NAME_KEY) or ""))
    if not key:
        return []
    suggestions = []
    for reading_list in ReadingList.objects.filter(user__isnull=True).exclude(
        pk__in=exclude
    ):
        if name_key(reading_list.name) != key:
            continue
        comparison = compare_documents(document, document_of(reading_list))
        if comparison.verdict == Verdict.UNRELATED:
            continue
        suggestions.append(
            Suggestion(
                pk=reading_list.pk,
                other_pk=0,
                verdict=str(comparison.verdict),
                combine=_suggests_combining(
                    comparison.verdict, either_is_tags=_is_tags_only(reading_list)
                ),
                overlap=round(comparison.overlap, 3),
            )
        )
    return sorted(suggestions, key=lambda item: (-item.combine, -item.overlap))


def _group_suggestions(lists: list[ReadingList]) -> list[Suggestion]:
    """Compare every pair of one name's lists; keep the ones to combine."""
    documents = {reading_list.pk: document_of(reading_list) for reading_list in lists}
    tags_only = {reading_list.pk: _is_tags_only(reading_list) for reading_list in lists}
    found = []
    for index, first in enumerate(lists):
        for second in lists[index + 1 :]:
            comparison = compare_documents(documents[first.pk], documents[second.pk])
            either_is_tags = tags_only[first.pk] or tags_only[second.pk]
            if _suggests_combining(comparison.verdict, either_is_tags=either_is_tags):
                found.append(
                    Suggestion(
                        pk=first.pk,
                        other_pk=second.pk,
                        verdict=str(comparison.verdict),
                        combine=True,
                        overlap=round(comparison.overlap, 3),
                    )
                )
    return found


def suggestions() -> list[Suggestion]:
    """Pairs of global lists of one name that look like one reading order."""
    groups: defaultdict[str, list[ReadingList]] = defaultdict(list)
    for reading_list in ReadingList.objects.filter(user__isnull=True).order_by("pk"):
        if key := name_key(reading_list.name):
            groups[key].append(reading_list)
    found = []
    for lists in groups.values():
        if len(lists) > 1:
            found += _group_suggestions(lists)
    return found

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

from comicbox.readinglists import Verdict, compare, normalize_series
from django.db import transaction
from django.db.models import Max
from django.utils.timezone import now

from codex.choices.limits import MAX_NAME_LEN
from codex.librarian.scribe.readinglists.combine import document_of, recombine
from codex.librarian.scribe.readinglists.documents import from_json
from codex.librarian.scribe.readinglists.matcher import ListMatcher
from codex.models.readinglist import (
    MAX_REF_LEN,
    MAX_REVISION_LEN,
    ReadingList,
    ReadingListEntry,
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
# What a comicbox source kind is when codex fetched it itself.
_COMICBOX_KINDS: Final[dict[str, str]] = {
    ReadingListSourceKind.URL: "url",
    ReadingListSourceKind.CATALOG: "catalog",
    ReadingListSourceKind.METRON_LIST: "metron-list",
    ReadingListSourceKind.METRON_ARC: "metron-arc",
    ReadingListSourceKind.COMICVINE_ARC: "comicvine-arc",
}


def name_key(name: str) -> str:
    """Return a name to group lists of one event by: no brackets, normalized."""
    return normalize_series(_NAME_NOISE_RE.sub(" ", name or ""))


def _fetched_source(document: Mapping[str, Any], kind: str) -> dict[str, Any]:
    """Return the document's own record of where it came from, if any."""
    wanted = _COMICBOX_KINDS.get(kind)
    sources = [source for source in document.get("sources") or () if source]
    for source in sources:
        if wanted and source.get("kind") == wanted:
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
            fetched.get("key") if kind == ReadingListSourceKind.CATALOG.value else None
        )
        return cls(
            kind=kind,
            ref=str(key or ref)[:MAX_REF_LEN],
            revision=str(fetched.get("revision") or "")[:MAX_REVISION_LEN],
            attribution_source=str(fetched.get("curator") or "")[:MAX_NAME_LEN],
            attribution_url=str(fetched.get("curator_url") or "")[:MAX_REF_LEN],
        )


def _next_rank(reading_list: ReadingList) -> int:
    top = ReadingListSource.objects.filter(reading_list=reading_list).aggregate(
        top=Max("rank")
    )["top"]
    return 0 if top is None else top + 1


def unique_name(name: str, user) -> str:
    """Personal list names are unique per owner: number a repeat."""
    if user is None:
        return name
    candidate, number = name, 2
    while ReadingList.objects.filter(user=user, name=candidate).exists():
        candidate = f"{name} ({number})"
        number += 1
    return candidate


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
            list_name = (name or document.get("name") or spec.ref)[:MAX_NAME_LEN]
            into = ReadingList.objects.create(
                name=unique_name(list_name, user),
                user=user,
                list_type=str(document.get("list_type") or "")[:64],
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
        source.ordered = document.get("ordered") is not False
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

    ``None`` means the remote said it is unchanged. Returns whether the
    list changed.
    """
    source.fetched_at = now()
    if document is None:
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
    source.ordered = document.get("ordered") is not False
    source.save()
    recombine(source.reading_list, matcher)
    return True


def remove_source(source: ReadingListSource) -> bool:
    """Remove a source and recompute; return whether its list survived."""
    reading_list = source.reading_list
    with transaction.atomic():
        source.delete()
        others = ReadingListSource.objects.filter(reading_list=reading_list).exists()
        manual = ReadingListEntry.objects.filter(
            reading_list=reading_list, manual=True
        ).exists()
        if not others and not manual:
            reading_list.delete()
            return False
        recombine(reading_list)
    return True


def rank_sources(reading_list: ReadingList, source_pks: Iterable[int]) -> None:
    """Reorder a list's sources; the first is the primary. Then recompute."""
    order = {pk: rank for rank, pk in enumerate(source_pks)}
    sources = list(ReadingListSource.objects.filter(reading_list=reading_list))
    tail = len(order)
    for source in sources:
        source.rank = order.get(source.pk, tail)
    ReadingListSource.objects.bulk_update(sources, ("rank",))
    recombine(reading_list)


def combine_lists(primary: ReadingList, others: Iterable[ReadingList]) -> ReadingList:
    """
    Combine lists into ``primary``, whose order wins.

    The others' sources join the primary's after its own, their hand-added
    entries come along, and the others are deleted. Removing a source later
    undoes the combination.
    """
    with transaction.atomic():
        rank = _next_rank(primary)
        for other in others:
            if other.pk == primary.pk:
                continue
            for source in ReadingListSource.objects.filter(reading_list=other).order_by(
                "rank", "pk"
            ):
                duplicate = ReadingListSource.objects.filter(
                    reading_list=primary, kind=source.kind, ref=source.ref
                ).exists()
                if duplicate:
                    continue
                source.reading_list = primary
                source.rank = rank
                source.save(update_fields=("reading_list", "rank", "updated_at"))
                rank += 1
            ReadingListEntry.objects.filter(reading_list=other, manual=True).update(
                reading_list=primary, position=10**9
            )
            other.delete()
        recombine(primary)
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
    key = name_key(str(document.get("name") or ""))
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

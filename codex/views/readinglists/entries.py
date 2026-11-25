"""
A reading list's entries: review, hand edits and reordering.

Hand edits are saved in Codex only and never change a comic file: a picked
comic, a hidden entry, an entry added by hand and a hand reorder all live
in the entry rows, and a recombine keeps them.
"""

from collections.abc import Iterable, Sequence
from typing import Any, Final

from comicbox.readinglists import parse_issue
from django.db import transaction
from django.db.models import Count, Max, Min, Q
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from codex.librarian.scribe.readinglists.live import (
    COLLECTION_KIND,
    LABEL_KEY,
    lock_list,
    reconcile_includers,
    reconcile_list,
    renumber,
)
from codex.librarian.scribe.readinglists.matcher import library_series_index
from codex.librarian.scribe.readinglists.references import (
    comic_references,
    issue_name,
)
from codex.models import Comic
from codex.models.readinglist import (
    DANGLING_Q,
    MISSING_Q,
    ReadingList,
    ReadingListEntry,
    ReadingListMatchTier,
    ReadingListSource,
)
from codex.views.readinglists.access import (
    ReadingListAccessView,
    can_edit,
    entries_acl_q,
    to_pk,
)

_CANDIDATE_LIMIT: Final = 50
_TAGGED_REFUSAL: Final = (
    "This issue's comic carries the list's story arc tag, so it stays that"
    " comic. Hide it to leave it out, or take the arc tag off the comic."
)
_FILTERS: Final = {
    "review": Q(needs_review=True, ignored=False),
    "missing": MISSING_Q,
    "hidden": Q(ignored=True),
    "all": Q(),
}


def _comic_repr(comic: Comic | None) -> dict[str, Any] | None:
    if comic is None:
        return None
    return {
        "pk": comic.pk,
        "seriesPk": comic.series_id,  # pyright: ignore[reportAttributeAccessIssue]
        "seriesName": comic.series.name if comic.series_id else "",  # pyright: ignore[reportAttributeAccessIssue]
        "volumeName": comic.volume.to_str(comic.volume.name, comic.volume.number_to)
        if comic.volume_id  # pyright: ignore[reportAttributeAccessIssue]
        else "",
        "issue": issue_name(comic.issue_number, comic.issue_suffix),
        "year": comic.year,
        "name": comic.name,
    }


def item_repr(item: ReadingListSource | None) -> dict[str, Any]:
    """Return a collection item: its kind, target, name for people, and if gone."""
    if item is None:
        return {
            "pk": None,
            "collection": "",
            "target_id": None,
            "label": "",
            "dangling": True,
        }
    label = (item.document or {}).get(LABEL_KEY) or item.ref
    return {
        "pk": item.pk,
        "collection": item.collection,
        "target_id": item.target_id,
        "label": label,
        "dangling": item.target_id is None,
    }


def entry_counts(list_pks: Iterable[int], shown_q: Q) -> dict[int, int]:
    """
    Count the entries each list shows a viewer, by list pk.

    ``shown_q`` is the viewer's :func:`shown_entries_q`, so a comic they may
    not see is not counted. A list with no such entry is absent.
    """
    rows = (
        ReadingListEntry.objects.filter(shown_q, reading_list_id__in=list_pks)
        .exclude(DANGLING_Q)
        .values("reading_list_id")
        .annotate(count=Count("pk"))
        .values_list("reading_list_id", "count")
    )
    return dict(rows)


def entry_count(reading_list: ReadingList, shown_q: Q) -> int:
    """Count the entries a list shows a viewer."""
    return entry_counts((reading_list.pk,), shown_q).get(reading_list.pk, 0)


def _live_refusal(entry: ReadingListEntry) -> str:
    label = item_repr(entry.live_source)["label"]
    return f"That issue is in this list through {label}. Remove {label} instead."


def entry_repr(entry: ReadingListEntry) -> dict[str, Any]:
    """
    Return an entry for the review screen.

    A live entry stores no names of its own: they come from its comic.
    """
    comic = entry.comic
    series_name, issue, year = entry.series_name, entry.issue, entry.year
    if entry.live_source_id is not None and comic is not None:  # pyright: ignore[reportAttributeAccessIssue]
        series_name = comic.series.name if comic.series_id else ""  # pyright: ignore[reportAttributeAccessIssue]
        issue = issue_name(comic.issue_number, comic.issue_suffix)
        year = comic.year
    return {
        "pk": entry.pk,
        "position": entry.position,
        "liveSource": entry.live_source_id,  # pyright: ignore[reportAttributeAccessIssue]
        "seriesName": series_name,
        "issue": issue,
        "year": year,
        "entryType": entry.entry_type,
        "sourceIds": entry.source_ids,
        "matchTier": entry.match_tier,
        "needsReview": entry.needs_review,
        "ignored": entry.ignored,
        "manual": entry.manual,
        "comic": _comic_repr(entry.comic),
    }


def _renumber(reading_list: ReadingList, ordered: Iterable[ReadingListEntry]) -> None:
    renumber([entry.pk for entry in ordered])
    reading_list.save()


def _settle(reading_list: ReadingList) -> None:
    """After a hand edit: sync the list's items, then the lists holding it."""
    reconcile_list(reading_list)
    reconcile_includers(reading_list)


def _is_sourced(reading_list: ReadingList) -> bool:
    """Whether a list has document or tags sources: its items sit at the end."""
    return (
        ReadingListSource.objects.filter(reading_list=reading_list)
        .exclude(kind=COLLECTION_KIND)
        .exists()
    )


def _boundary(ordered: list[ReadingListEntry], position: int | None) -> int:
    """Clamp an insert position, and move it out of a block to the block's start."""
    at = len(ordered) if position is None else max(0, min(position, len(ordered)))
    while 0 < at < len(ordered):
        block = ordered[at].live_source_id  # pyright: ignore[reportAttributeAccessIssue]
        if block is None or ordered[at - 1].live_source_id != block:  # pyright: ignore[reportAttributeAccessIssue]
            break
        at -= 1
    return at


def _items_repr(reading_list: ReadingList, acl_q: Q) -> list[dict[str, Any]]:
    """Each collection item as one editor row: its count and where it starts."""
    stats = {
        row["live_source_id"]: row
        for row in ReadingListEntry.objects.filter(
            acl_q, reading_list=reading_list, live_source__isnull=False
        )
        .values("live_source_id")
        .annotate(count=Count("pk"), start=Min("position"))
    }
    items = []
    for item in ReadingListSource.objects.filter(
        reading_list=reading_list, kind=COLLECTION_KIND
    ).order_by("rank", "pk"):
        row = item_repr(item)
        stat = stats.get(item.pk, {})
        row["count"] = stat.get("count", 0)
        row["position"] = stat.get("start")
        items.append(row)
    return items


# What ``entry_repr`` reads: not an entry's reference or a comic's text.
_ENTRY_REPR_FIELDS: Final = (
    "pk",
    "position",
    "live_source_id",
    "series_name",
    "issue",
    "year",
    "entry_type",
    "source_ids",
    "match_tier",
    "needs_review",
    "ignored",
    "manual",
    "comic__id",
    "comic__series_id",
    "comic__volume_id",
    "comic__issue_number",
    "comic__issue_suffix",
    "comic__year",
    "comic__name",
    "comic__series__name",
    "comic__volume__name",
    "comic__volume__number_to",
)


def _entries(reading_list: ReadingList):
    return (
        ReadingListEntry.objects.filter(reading_list=reading_list)
        .select_related("comic", "comic__series", "comic__volume")
        .only(*_ENTRY_REPR_FIELDS)
        .order_by("position", "pk")
    )


def _order(reading_list: ReadingList) -> list[ReadingListEntry]:
    """Return the list's entries in order, lean: for reorders and inserts."""
    return list(
        ReadingListEntry.objects.filter(reading_list=reading_list)
        .order_by("position", "pk")
        .only("pk", "position", "live_source_id")
    )


class ReadingListEntriesView(ReadingListAccessView):
    """GET a list's entries; POST comics onto it by hand."""

    def get(self, *_args, **_kwargs) -> Response:
        """
        Return the entries, narrowed by ``?filter=review|missing|hidden|all``.

        An entry whose comic the editor may not see is left out, as it is
        everywhere else the list is read.
        """
        reading_list = self.get_reading_list()
        filter_q = _FILTERS.get(self.request.GET.get("filter", "all"), Q())
        acl_q = entries_acl_q(self, self.request.user)
        entries = [
            entry_repr(entry)
            for entry in _entries(reading_list).filter(acl_q & filter_q)
        ]
        items = _items_repr(reading_list, acl_q)
        return Response({"entries": entries, "items": items, "editable": True})

    def post(self, *_args, **_kwargs) -> Response:
        """
        Add comics by hand, after ``position`` or at the end.

        Each is a manual entry: it survives any recombine, and its
        reference is built from the comic so it can be found again.
        """
        reading_list = self.get_reading_list()
        pks = self.visible_comic_pks(self.data_value("comics"))
        position = self.data_value("position")
        if position is not None:
            position = to_pk(position, "position")
        added = add_comics(reading_list, pks, position)
        return Response({"added": added})


def _hand_entries(
    reading_list: ReadingList, wanted: Sequence[int]
) -> list[ReadingListEntry]:
    """Make the hand-added entries of the comics, in order, that exist."""
    references = comic_references(wanted)
    comics = {
        comic.pk: comic
        for comic in Comic.objects.filter(pk__in=wanted).select_related("series")
    }
    return [
        ReadingListEntry(
            reading_list=reading_list,
            comic=comic,
            reference=references.get(pk, {}),
            series_name=comic.series.name if comic.series_id else "",  # pyright: ignore[reportAttributeAccessIssue]
            issue=issue_name(comic.issue_number, comic.issue_suffix),
            year=comic.year,
            match_tier=ReadingListMatchTier.MANUAL,
            manual=True,
        )
        for pk in wanted
        if (comic := comics.get(pk)) is not None
    ]


def add_comics(
    reading_list: ReadingList,
    pks: list[int],
    position: int | None = None,
    *,
    settle: bool = True,
) -> int:
    """
    Put comics into a list by hand, in order, at ``position`` or the end.

    A comic the list already shows is skipped; one it holds hidden shows
    again, where it was, as hand-added: a source's row then outlives its
    source, as a folded entry does. One a collection item delivers becomes
    a hand entry, and the item stops delivering it. An insert inside a
    block goes in before the block. ``settle=False`` leaves syncing the
    list and its holders to a caller that changes more of the list first.
    """
    if not pks:
        return 0
    own = ReadingListEntry.objects.filter(
        reading_list=reading_list, live_source__isnull=True, comic_id__in=pks
    )
    shown = set(own.filter(ignored=False).values_list("comic_id", flat=True))
    hidden = set(own.filter(ignored=True).values_list("comic_id", flat=True)) - shown
    wanted = [pk for pk in dict.fromkeys(pks) if pk not in shown | hidden]
    new_entries = _hand_entries(reading_list, wanted)
    if not new_entries and not hidden:
        return 0
    with transaction.atomic():
        lock_list(reading_list)
        own.filter(ignored=True, comic_id__in=hidden).update(ignored=False, manual=True)
        ordered = _order(reading_list)
        at = _boundary(ordered, position)
        ReadingListEntry.objects.bulk_create(new_entries)
        _renumber(reading_list, ordered[:at] + new_entries + ordered[at:])
        if settle:
            reconcile_list(reading_list)
    if settle:
        reconcile_includers(reading_list)
    return len(new_entries) + len(hidden)


class ReadingListEntryView(ReadingListAccessView):
    """PATCH one entry: pick its comic, hide it, clear its review flag."""

    def _entry(self, reading_list: ReadingList) -> ReadingListEntry:
        entry = (
            ReadingListEntry.objects.filter(
                entries_acl_q(self, self.request.user),
                reading_list=reading_list,
                pk=self.kwargs["entry_pk"],
            )
            .select_related("comic", "comic__series", "comic__volume", "live_source")
            .first()
        )
        if entry is None:
            reason = "No such issue in this list."
            raise ValidationError(reason)
        if entry.live_source_id is not None:  # pyright: ignore[reportAttributeAccessIssue]
            raise ValidationError(_live_refusal(entry))
        return entry

    def _pick(self, entry: ReadingListEntry, comic_pk) -> None:
        if entry.match_tier == ReadingListMatchTier.TAGGED.value:
            # A recompute would put the tagged comic back, and the entry
            # would stop being the list's own.
            raise ValidationError(_TAGGED_REFUSAL)
        if comic_pk is None:
            # A person said the library does not have it: no rematch or
            # recombine may pick a comic for it again.
            entry.comic = None
            entry.match_tier = ReadingListMatchTier.MARKED_MISSING
            entry.needs_review = False
            return
        acl = self.get_acl_filter(Comic, self.request.user)
        comic = Comic.objects.filter(acl, pk=to_pk(comic_pk, "comic")).first()
        if comic is None:
            reason = "No such comic."
            raise ValidationError(reason)
        entry.comic = comic
        entry.match_tier = ReadingListMatchTier.MANUAL
        entry.needs_review = False

    def patch(self, *_args, **_kwargs) -> Response:
        """Change what was given: ``comic``, ``ignored``, ``needsReview``."""
        reading_list = self.get_reading_list()
        entry = self._entry(reading_list)
        data = self.request.data
        if "comic" in data:
            self._pick(entry, data["comic"])
            # A pick replaces the comic a folded entry was added for: it is
            # its source row's again, and the pick holds on that row, which
            # is never a tagged one.
            entry.manual = entry.manual and not entry.source_ids
        if "ignored" in data:
            entry.ignored = bool(data["ignored"])
        if "needs_review" in data:
            entry.needs_review = bool(data["needs_review"])
        entry.save()
        reading_list.save()
        _settle(reading_list)
        entry = self._entry(reading_list)
        return Response(entry_repr(entry))

    def delete(self, *_args, **_kwargs) -> Response:
        """
        Remove a hand-added entry; any other entry is hidden instead.

        A hand-added entry a source row holds is hidden too: the source
        would bring it back.
        """
        reading_list = self.get_reading_list()
        entry = self._entry(reading_list)
        deleted = entry.manual and not entry.source_ids
        with transaction.atomic():
            if deleted:
                entry.delete()
                _renumber(reading_list, _order(reading_list))
            else:
                entry.ignored = True
                entry.save()
                reading_list.save()
        _settle(reading_list)
        return Response({"deleted": deleted})


def remove_comics(
    reading_list: ReadingList, pks: Iterable[int], *, settle: bool = True
) -> dict[str, Any]:
    """
    Take comics out of a list, in place; say how many of each kind.

    An entry added by hand goes; any other is hidden, since its source
    would bring it back, a hand-added one a source row holds included. A
    comic a collection item delivers is refused, and the answer names the
    item, to remove instead.
    """
    pks = list(pks)
    if not pks:
        return {"removed": 0, "hidden": 0, "refused": []}
    entries = ReadingListEntry.objects.filter(
        reading_list=reading_list, comic_id__in=pks
    )
    refused = [
        {"comic": entry.comic_id, "item": item_repr(entry.live_source)}  # pyright: ignore[reportAttributeAccessIssue]
        for entry in entries.filter(live_source__isnull=False).select_related(
            "live_source"
        )
    ]
    listed = entries.filter(live_source__isnull=True)
    # Only what no source supplies is the list's own to delete.
    own = listed.filter(source_ids=[])
    with transaction.atomic():
        lock_list(reading_list)
        removed, _ = own.filter(manual=True).delete()
        hidden = listed.filter(ignored=False).update(ignored=True)
        if removed:
            _renumber(reading_list, _order(reading_list))
        else:
            reading_list.save()
    if settle and (removed or hidden):
        _settle(reading_list)
    return {"removed": removed, "hidden": hidden, "refused": refused}


class ReadingListReorderView(ReadingListAccessView):
    """
    POST an entry's or a collection item's new position.

    A hand reorder locks the list's order. A live entry moves only with its
    item. On a list with document or tags sources the items stay at the
    end; on a hand-made list an item's block moves as a unit.
    """

    @staticmethod
    def _move_entry(
        ordered: list[ReadingListEntry], entry_pk: int, position: int, *, sourced: bool
    ) -> list[ReadingListEntry]:
        moving = next((entry for entry in ordered if entry.pk == entry_pk), None)
        if moving is None:
            reason = "No such issue in this list."
            raise ValidationError(reason)
        if moving.live_source_id is not None:  # pyright: ignore[reportAttributeAccessIssue]
            reason = "That issue moves with its collection: move the collection."
            raise ValidationError(reason)
        ordered.remove(moving)
        if sourced:
            others = sum(1 for e in ordered if e.live_source_id is None)  # pyright: ignore[reportAttributeAccessIssue]
            position = min(position, others)
        at = _boundary(ordered, position)
        return [*ordered[:at], moving, *ordered[at:]]

    @staticmethod
    def _move_item(
        reading_list: ReadingList,
        ordered: list[ReadingListEntry],
        item_pk: int,
        position: int,
    ) -> list[ReadingListEntry]:
        item = ReadingListSource.objects.filter(
            reading_list=reading_list, kind=COLLECTION_KIND, pk=item_pk
        ).first()
        if item is None:
            reason = "No such collection in this list."
            raise ValidationError(reason)
        block = [e for e in ordered if e.live_source_id == item.pk]  # pyright: ignore[reportAttributeAccessIssue]
        rest = [e for e in ordered if e.live_source_id != item.pk]  # pyright: ignore[reportAttributeAccessIssue]
        at = _boundary(rest, position)
        if not block:
            # An empty block is placed by its hint: other entries before it.
            item.position = sum(1 for e in rest[:at] if e.live_source_id is None)  # pyright: ignore[reportAttributeAccessIssue]
            item.save(update_fields=("position",))
        return [*rest[:at], *block, *rest[at:]]

    def post(self, *_args, **_kwargs) -> Response:
        """Move ``entry`` or ``item`` to ``position``, 0-based; lock the order."""
        reading_list = self.get_reading_list()
        position = to_pk(self.data_value("position"), "position")
        item_pk = self.data_value("item")
        sourced = _is_sourced(reading_list)
        with transaction.atomic():
            lock_list(reading_list)
            ordered = _order(reading_list)
            if item_pk is None:
                entry_pk = to_pk(self.data_value("entry"), "entry")
                ordered = self._move_entry(ordered, entry_pk, position, sourced=sourced)
            elif sourced:
                reason = "Collections stay at the end of a list with sources."
                raise ValidationError(reason)
            else:
                ordered = self._move_item(
                    reading_list, ordered, to_pk(item_pk, "item"), position
                )
            reading_list.order_locked = True
            _renumber(reading_list, ordered)
            reconcile_list(reading_list)
        reconcile_includers(reading_list)
        return Response({"position": position})


class ReadingListAcceptView(ReadingListAccessView):
    """POST: accept every best guess, clearing the review flags."""

    def post(self, *_args, **_kwargs) -> Response:
        """Clear the list's review flags."""
        reading_list = self.get_reading_list()
        count = ReadingListEntry.objects.filter(
            reading_list=reading_list, needs_review=True
        ).update(needs_review=False)
        reading_list.save()
        return Response({"accepted": count})


class ReadingListCandidatesView(ReadingListAccessView):
    """GET comics that could be an entry: the picker of the review screen."""

    def _series_pks(self, entry: ReadingListEntry, query: str) -> set[int] | None:
        if query:
            return None
        return library_series_index().series_for(entry.reference or {})

    def get(self, *_args, **_kwargs) -> Response:
        """Search by ``?q=`` series name, else by the entry's own series names."""
        reading_list = self.get_reading_list()
        entry = (
            ReadingListEntry.objects.filter(
                entries_acl_q(self, self.request.user),
                reading_list=reading_list,
                pk=self.kwargs["entry_pk"],
            )
            .select_related("live_source")
            .first()
        )
        if entry is None:
            reason = "No such issue in this list."
            raise ValidationError(reason)
        if entry.live_source_id is not None:  # pyright: ignore[reportAttributeAccessIssue]
            raise ValidationError(_live_refusal(entry))
        query = (self.request.GET.get("q") or "").strip()
        qs = Comic.objects.filter(self.get_acl_filter(Comic, self.request.user))
        series_pks = self._series_pks(entry, query)
        if series_pks is None:
            qs = qs.filter(series__name__icontains=query)
        else:
            qs = qs.filter(series_id__in=series_pks)
        if entry.issue:
            parsed = parse_issue(entry.issue)
            same_issue = qs.filter(
                issue_number=parsed.number, issue_suffix__iexact=parsed.suffix
            )
            if same_issue.exists():
                qs = same_issue
        comics = qs.select_related("series", "volume").order_by(
            "series__sort_name", "volume__name", "issue_number", "pk"
        )[:_CANDIDATE_LIMIT]
        return Response({"candidates": [_comic_repr(comic) for comic in comics]})


def next_position(reading_list: ReadingList) -> int:
    """Return the position after the list's last entry."""
    top = ReadingListEntry.objects.filter(reading_list=reading_list).aggregate(
        top=Max("position")
    )["top"]
    return 0 if top is None else top + 1


__all__ = (
    "ReadingListAcceptView",
    "ReadingListCandidatesView",
    "ReadingListEntriesView",
    "ReadingListEntryView",
    "ReadingListReorderView",
    "add_comics",
    "can_edit",
    "entry_repr",
    "item_repr",
    "next_position",
    "remove_comics",
)

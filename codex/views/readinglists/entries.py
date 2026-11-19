"""
A reading list's entries: review, hand edits and reordering.

Hand edits are saved in Codex only and never change a comic file: a picked
comic, a hidden entry, an entry added by hand and a hand reorder all live
in the entry rows, and a recombine keeps them.
"""

from collections.abc import Iterable
from typing import Any, Final

from comicbox.readinglists import parse_issue
from django.db import transaction
from django.db.models import Max, Q
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from codex.librarian.scribe.readinglists.matcher import SeriesNameIndex
from codex.librarian.scribe.readinglists.references import (
    comic_references,
    issue_name,
)
from codex.models import Comic
from codex.models.readinglist import (
    ReadingList,
    ReadingListEntry,
    ReadingListMatchTier,
)
from codex.views.readinglists.access import (
    ReadingListAccessView,
    can_edit,
    entries_acl_q,
    to_pk,
    to_pks,
)

_CANDIDATE_LIMIT: Final = 50
_FILTERS: Final = {
    "review": Q(needs_review=True, ignored=False),
    "missing": Q(comic__isnull=True, ignored=False),
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


def entry_repr(entry: ReadingListEntry) -> dict[str, Any]:
    """Return an entry for the review screen."""
    return {
        "pk": entry.pk,
        "position": entry.position,
        "seriesName": entry.series_name,
        "issue": entry.issue,
        "year": entry.year,
        "entryType": entry.entry_type,
        "sourceIds": entry.source_ids,
        "matchTier": entry.match_tier,
        "needsReview": entry.needs_review,
        "ignored": entry.ignored,
        "manual": entry.manual,
        "comic": _comic_repr(entry.comic),
    }


def _renumber(reading_list: ReadingList, ordered: Iterable[ReadingListEntry]) -> None:
    entries = []
    for position, entry in enumerate(ordered):
        if entry.position != position:
            entry.position = position
            entries.append(entry)
    ReadingListEntry.objects.bulk_update(entries, ("position", "updated_at"))
    reading_list.save()


def _entries(reading_list: ReadingList):
    return (
        ReadingListEntry.objects.filter(reading_list=reading_list)
        .select_related("comic", "comic__series", "comic__volume")
        .order_by("position", "pk")
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
        return Response({"entries": entries, "editable": True})

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


def add_comics(
    reading_list: ReadingList, pks: list[int], position: int | None = None
) -> int:
    """Put comics into a list by hand, in order, at ``position`` or the end."""
    if not pks:
        return 0
    references = comic_references(pks)
    comics = {
        comic.pk: comic
        for comic in Comic.objects.filter(pk__in=pks).select_related("series")
    }
    with transaction.atomic():
        ordered = list(
            ReadingListEntry.objects.filter(reading_list=reading_list).order_by(
                "position", "pk"
            )
        )
        at = len(ordered) if position is None else max(0, min(position, len(ordered)))
        new_entries = []
        for pk in pks:
            comic = comics.get(pk)
            if comic is None:
                continue
            new_entries.append(
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
            )
        ReadingListEntry.objects.bulk_create(new_entries)
        merged = ordered[:at] + new_entries + ordered[at:]
        _renumber(reading_list, merged)
    return len(new_entries)


class ReadingListEntryView(ReadingListAccessView):
    """PATCH one entry: pick its comic, hide it, clear its review flag."""

    def _entry(self, reading_list: ReadingList) -> ReadingListEntry:
        entry = (
            ReadingListEntry.objects.filter(
                entries_acl_q(self, self.request.user),
                reading_list=reading_list,
                pk=self.kwargs["entry_pk"],
            )
            .select_related("comic", "comic__series", "comic__volume")
            .first()
        )
        if entry is None:
            reason = "No such issue in this list."
            raise ValidationError(reason)
        return entry

    def _pick(self, entry: ReadingListEntry, comic_pk) -> None:
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
        if "ignored" in data:
            entry.ignored = bool(data["ignored"])
        if "needs_review" in data:
            entry.needs_review = bool(data["needs_review"])
        entry.save()
        reading_list.save()
        entry = self._entry(reading_list)
        return Response(entry_repr(entry))

    def delete(self, *_args, **_kwargs) -> Response:
        """Remove a hand-added entry; any other entry is hidden instead."""
        reading_list = self.get_reading_list()
        entry = self._entry(reading_list)
        if entry.manual:
            entry.delete()
            _renumber(reading_list, _entries(reading_list))
        else:
            entry.ignored = True
            entry.save()
            reading_list.save()
        return Response({"deleted": entry.manual})


class ReadingListRemoveView(ReadingListAccessView):
    """
    POST ``{comics}``: take comics out of a list, in place.

    The entry DELETE's rule for each of their entries: one added by hand
    goes, any other is hidden, since its source would bring it back.
    """

    def post(self, *_args, **_kwargs) -> Response:
        """Remove or hide each entry of the comics; say how many of each."""
        reading_list = self.get_reading_list()
        pks = to_pks(self.data_value("comics"), "comics")
        entries = ReadingListEntry.objects.filter(
            reading_list=reading_list, comic_id__in=pks
        )
        with transaction.atomic():
            removed, _ = entries.filter(manual=True).delete()
            hidden = entries.filter(manual=False, ignored=False).update(ignored=True)
            if removed:
                _renumber(reading_list, _entries(reading_list))
            else:
                reading_list.save()
        return Response({"removed": removed, "hidden": hidden})


class ReadingListReorderView(ReadingListAccessView):
    """POST an entry's new position. A hand reorder locks the list's order."""

    def post(self, *_args, **_kwargs) -> Response:
        """Move ``entry`` to ``position``, 0-based, and lock the order."""
        reading_list = self.get_reading_list()
        entry_pk = to_pk(self.data_value("entry"), "entry")
        position = to_pk(self.data_value("position"), "position")
        with transaction.atomic():
            ordered = list(_entries(reading_list))
            moving = next((entry for entry in ordered if entry.pk == entry_pk), None)
            if moving is None:
                reason = "No such issue in this list."
                raise ValidationError(reason)
            ordered.remove(moving)
            ordered.insert(max(0, min(position, len(ordered))), moving)
            reading_list.order_locked = True
            _renumber(reading_list, ordered)
        return Response({"position": moving.position})


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
        return SeriesNameIndex().series_for(entry.reference or {})

    def get(self, *_args, **_kwargs) -> Response:
        """Search by ``?q=`` series name, else by the entry's own series names."""
        reading_list = self.get_reading_list()
        entry = ReadingListEntry.objects.filter(
            entries_acl_q(self, self.request.user),
            reading_list=reading_list,
            pk=self.kwargs["entry_pk"],
        ).first()
        if entry is None:
            reason = "No such issue in this list."
            raise ValidationError(reason)
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
    "ReadingListRemoveView",
    "ReadingListReorderView",
    "add_comics",
    "can_edit",
    "entry_repr",
    "next_position",
)

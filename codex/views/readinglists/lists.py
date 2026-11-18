"""
Reading lists for their owners: create, rename, duplicate, delete, export.

Signed-in users make personal lists by hand; admins own the global ones.
A personal list is saved in Codex only and never changes a comic file.
"""

import re
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Final

from comicbox.readinglists import ReadingListError, dumps
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from codex.choices.limits import MAX_NAME_LEN
from codex.librarian.scribe.readinglists.combine import document_of
from codex.librarian.scribe.readinglists.documents import from_json
from codex.librarian.scribe.readinglists.references import comic_references
from codex.librarian.scribe.readinglists.service import unique_name
from codex.models.readinglist import (
    ReadingList,
    ReadingListEntry,
    ReadingListMatchTier,
    ReadingListSource,
    ReadingListSourceKind,
)
from codex.views.readinglists.access import ReadingListAccessView, can_edit
from codex.views.readinglists.entries import add_comics, editable_lists_q

# Codex's source kind -> comicbox's, for export.
_COMICBOX_KINDS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        ReadingListSourceKind.TAGS: "tags",
        ReadingListSourceKind.UPLOAD: "file",
        ReadingListSourceKind.URL: "url",
        ReadingListSourceKind.CATALOG: "catalog",
        ReadingListSourceKind.METRON_LIST: "metron-list",
        ReadingListSourceKind.METRON_ARC: "metron-arc",
        ReadingListSourceKind.COMICVINE_ARC: "comicvine-arc",
    }
)
_KEYLESS_KINDS: Final = frozenset(
    {ReadingListSourceKind.TAGS, ReadingListSourceKind.UPLOAD}
)
# Export format -> (comicbox format token, suffix, content type). Lists
# export in the ComicRack formats only; comicbox's own YAML and JSON reading
# list formats are not offered.
EXPORT_FORMATS: Final = MappingProxyType(
    {
        "cbl": ("cbl", ".cbl", "application/xml"),
        "json-cbl": ("json-cbl", ".json", "application/json"),
    }
)
_UNSAFE_FILENAME_RE: Final = re.compile(r"[^\w\- .()\[\]]+")


def _merge_ids(target: dict, source: dict) -> None:
    for key in ("identifiers",):
        if ids := source.get(key):
            merged = dict(ids)
            merged.update(target.get(key) or {})
            target[key] = merged


def _with_comic(reference: dict, comic: dict | None) -> dict:
    """Add what the matched comic knows that the entry does not, ids too."""
    entry = deepcopy(reference) or {}
    if not comic:
        return entry
    for key, value in comic.items():
        entry.setdefault(key, deepcopy(value))
    _merge_ids(entry, comic)
    if comic.get("series") and entry.get("series"):
        _merge_ids(entry["series"], comic["series"])
    return entry


def _export_entries(reading_list: ReadingList) -> list[dict[str, Any]]:
    """Each shown entry's reference, with the ids of the comic it matched."""
    entries = list(
        ReadingListEntry.objects.filter(reading_list=reading_list, ignored=False)
        .order_by("position", "pk")
        .values_list("reference", "comic_id")
    )
    comics = comic_references(pk for _, pk in entries if pk)
    exported = (
        _with_comic(reference, comics.get(comic_pk) if comic_pk else None)
        for reference, comic_pk in entries
    )
    return [entry for entry in exported if entry]


def _export_sources(reading_list: ReadingList) -> list[dict[str, str]]:
    sources = []
    for source in ReadingListSource.objects.filter(reading_list=reading_list).order_by(
        "rank", "pk"
    ):
        exported = {"kind": _COMICBOX_KINDS.get(source.kind, source.kind)}
        if source.kind not in _KEYLESS_KINDS:
            exported["key"] = source.ref
        exported.update(
            {
                key: value
                for key, value in (
                    ("revision", source.revision),
                    ("curator", source.attribution_source),
                    ("curator_url", source.attribution_url),
                )
                if value
            }
        )
        sources.append(exported)
    # Keep the list's own UUID, or every json-cbl export mints a new one.
    sources.append({"kind": "json-cbl", "key": str(reading_list.uuid)})
    return sources


def export_document(reading_list: ReadingList) -> dict[str, Any]:
    """Return the list as a comicbox model, ready to write in any format."""
    document = document_of(reading_list)
    document["entries"] = _export_entries(reading_list)
    document["sources"] = _export_sources(reading_list)
    return from_json(document)


def export_filename(reading_list: ReadingList, suffix: str) -> str:
    """Name an exported file after its list."""
    stem = (
        _UNSAFE_FILENAME_RE.sub("_", reading_list.name).strip(" ._") or "reading-list"
    )
    return f"{stem}{suffix}"


def _validated_name(data) -> str:
    name = str(data.get("name") or "").strip()
    if not name or len(name) > MAX_NAME_LEN:
        reason = f"A name of 1 to {MAX_NAME_LEN} characters is required."
        raise ValidationError(reason)
    return name


def list_repr(reading_list: ReadingList, user) -> dict[str, Any]:
    """Return a list for menus and the My Lists dialog."""
    return {
        "pk": reading_list.pk,
        "name": reading_list.name,
        "personal": reading_list.user_id is not None,  # pyright: ignore[reportAttributeAccessIssue]
        "count": getattr(reading_list, "count", None),
        "editable": can_edit(user, reading_list),
    }


class ReadingListsView(ReadingListAccessView):
    """GET the lists a user may add to; POST a new personal list."""

    permission_classes = (IsAuthenticated,)

    def get(self, *_args, **_kwargs) -> Response:
        """Return the user's own lists, and the global ones for an admin."""
        user = self.request.user
        lists = (
            ReadingList.objects.filter(editable_lists_q(user))
            .annotate(count=Count("entries", filter=Q(entries__ignored=False)))
            .order_by("user_id", "sort_name", "pk")
        )
        return Response({"lists": [list_repr(rl, user) for rl in lists]})

    def post(self, *_args, **_kwargs) -> Response:
        """Make a personal list, empty or holding ``comics``."""
        name = _validated_name(self.request.data)
        try:
            with transaction.atomic():
                reading_list = ReadingList.objects.create(
                    name=name, user=self.request.user
                )
        except IntegrityError as exc:
            reason = "You already have a reading list with that name."
            raise ValidationError(reason) from exc
        if comics := self.request.data.get("comics"):
            add_comics(reading_list, [int(pk) for pk in comics])
        return Response(list_repr(reading_list, self.request.user), status=201)


class ReadingListDetailView(ReadingListAccessView):
    """PATCH a list's name; DELETE a list."""

    def patch(self, *_args, **_kwargs) -> Response:
        """Rename a list. A recombine leaves a hand-given name alone."""
        reading_list = self.get_reading_list()
        reading_list.name = _validated_name(self.request.data)
        edited: set[str] = set(reading_list.edited_fields or ())
        edited.add("name")
        reading_list.edited_fields = sorted(edited)
        try:
            reading_list.save()
        except IntegrityError as exc:
            reason = "You already have a reading list with that name."
            raise ValidationError(reason) from exc
        return Response(list_repr(reading_list, self.request.user))

    def delete(self, *_args, **_kwargs) -> Response:
        """Delete a list. Its comics and their files are untouched."""
        reading_list = self.get_reading_list()
        reading_list.delete()
        return Response({"deleted": True})


class ReadingListDuplicateView(ReadingListAccessView):
    """POST: copy a visible list into a personal list of one's own."""

    permission_classes = (IsAuthenticated,)

    def post(self, *_args, **_kwargs) -> Response:
        """Copy every shown entry, as entries added by hand."""
        original = self.get_reading_list(edit=False)
        name = str(self.request.data.get("name") or f"{original.name} (copy)")[
            :MAX_NAME_LEN
        ]
        with transaction.atomic():
            copy = ReadingList.objects.create(
                name=unique_name(name, self.request.user),
                user=self.request.user,
                description=original.description,
                list_type=original.list_type,
                start_year=original.start_year,
                end_year=original.end_year,
                order_locked=True,
            )
            entries = ReadingListEntry.objects.filter(
                reading_list=original, ignored=False
            ).order_by("position", "pk")
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
        return Response(list_repr(copy, self.request.user), status=201)


class ReadingListExportView(ReadingListAccessView):
    """
    GET a list as a file: ``?fmt=cbl|json-cbl``.

    Not ``format``: DRF reads that query parameter to choose a renderer.
    """

    def get(self, *_args, **_kwargs):
        """Write the list; matched entries carry their comic's ids."""
        reading_list = self.get_reading_list(edit=False)
        user = self.request.user
        if not (getattr(user, "is_staff", False) or reading_list.user_id == user.pk):  # pyright: ignore[reportAttributeAccessIssue]
            reason = "Only the list's owner or an admin may export it."
            raise PermissionDenied(reason)
        fmt = self.request.GET.get("fmt", "cbl")
        if fmt not in EXPORT_FORMATS:
            reason = f"Unknown format {fmt!r}. Known: {', '.join(EXPORT_FORMATS)}."
            raise ValidationError(reason)
        token, suffix, content_type = EXPORT_FORMATS[fmt]
        try:
            text = dumps(export_document(reading_list), token)
        except ReadingListError as exc:
            raise ValidationError(str(exc)) from exc
        response = HttpResponse(text, content_type=f"{content_type}; charset=utf-8")
        filename = export_filename(reading_list, suffix)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

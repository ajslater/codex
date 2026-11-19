"""
Reading lists for their owners: create, rename, duplicate, delete, export.

Signed-in users make personal lists by hand; admins own the global ones.
A personal list is saved in Codex only and never changes a comic file.
"""

import re
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Final

from comicbox.readinglists import (
    ENTRIES_KEY,
    SOURCE_CURATOR_KEY,
    SOURCE_CURATOR_URL_KEY,
    SOURCE_KEY_KEY,
    SOURCE_KIND_KEY,
    SOURCE_REVISION_KEY,
    SOURCES_KEY,
    ReadingListError,
    SourceKind,
    dumps,
)
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from codex.choices.limits import MAX_NAME_LEN
from codex.librarian.scribe.readinglists.combine import document_of
from codex.librarian.scribe.readinglists.documents import COMICBOX_KINDS, from_json
from codex.librarian.scribe.readinglists.references import comic_references
from codex.librarian.scribe.readinglists.service import copy_list
from codex.models.readinglist import (
    ReadingList,
    ReadingListEntry,
    ReadingListSource,
    ReadingListSourceKind,
)
from codex.views.readinglists.access import (
    ReadingListAccessView,
    can_edit,
    menu_lists_q,
)
from codex.views.readinglists.details import continue_comic
from codex.views.readinglists.entries import add_comics

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
_TRUE_VALUES: Final = frozenset({"1", "true"})


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


def _export_entries(reading_list: ReadingList, shown_q: Q) -> list[dict[str, Any]]:
    """Each shown entry's reference, with the ids of the comic it matched."""
    entries = list(
        ReadingListEntry.objects.filter(shown_q, reading_list=reading_list)
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
        exported = {SOURCE_KIND_KEY: COMICBOX_KINDS.get(source.kind, source.kind)}
        if source.kind not in _KEYLESS_KINDS:
            exported[SOURCE_KEY_KEY] = source.ref
        exported.update(
            {
                key: value
                for key, value in (
                    (SOURCE_REVISION_KEY, source.revision),
                    (SOURCE_CURATOR_KEY, source.attribution_source),
                    (SOURCE_CURATOR_URL_KEY, source.attribution_url),
                )
                if value
            }
        )
        sources.append(exported)
    # Keep the list's own UUID, or every json-cbl export mints a new one.
    sources.append(
        {
            SOURCE_KIND_KEY: SourceKind.JSON_CBL.value,
            SOURCE_KEY_KEY: str(reading_list.uuid),
        }
    )
    return sources


def export_document(reading_list: ReadingList, shown_q: Q) -> dict[str, Any]:
    """
    Return the list as a comicbox model, ready to write in any format.

    ``shown_q`` picks the entries the exporter sees.
    """
    document = document_of(reading_list)
    document[ENTRIES_KEY] = _export_entries(reading_list, shown_q)
    document[SOURCES_KEY] = _export_sources(reading_list)
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


def _entry_count(reading_list: ReadingList) -> int:
    """Count the entries a list shows: the menu's annotation, else a query."""
    count = getattr(reading_list, "count", None)
    if count is None:
        count = ReadingListEntry.objects.filter(
            reading_list=reading_list, ignored=False
        ).count()
    return count


def list_repr(reading_list: ReadingList, user) -> dict[str, Any]:
    """Return a list for menus and the My Lists dialog."""
    return {
        "pk": reading_list.pk,
        "name": reading_list.name,
        "personal": reading_list.user_id is not None,  # pyright: ignore[reportAttributeAccessIssue]
        "count": _entry_count(reading_list),
        "editable": can_edit(user, reading_list),
    }


class ReadingListsView(ReadingListAccessView):
    """GET the lists a user may add to; POST a new personal list."""

    permission_classes = (IsAuthenticated,)

    def get(self, *_args, **_kwargs) -> Response:
        """Return the user's own lists, and for an admin the curated global ones."""
        user = self.request.user
        lists = (
            ReadingList.objects.filter(menu_lists_q(user))
            .annotate(count=Count("entries", filter=Q(entries__ignored=False)))
            .order_by("user_id", "sort_name", "pk")
        )
        return Response({"lists": [list_repr(rl, user) for rl in lists]})

    def post(self, *_args, **_kwargs) -> Response:
        """Make a personal list, empty or holding the ``comics`` the user sees."""
        name = _validated_name(self.request.data)
        pks = self.visible_comic_pks(self.request.data.get("comics"))
        try:
            with transaction.atomic():
                reading_list = ReadingList.objects.create(
                    name=name, user=self.request.user
                )
        except IntegrityError as exc:
            reason = "You already have a reading list with that name."
            raise ValidationError(reason) from exc
        add_comics(reading_list, pks)
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
        """Copy every entry the user sees, as entries added by hand."""
        original = self.get_reading_list(edit=False)
        name = str(self.request.data.get("name") or f"{original.name} (copy)")
        copy = copy_list(
            original,
            user=self.request.user,
            name=name,
            entries_q=self.shown_entries_q(),
        )
        return Response(list_repr(copy, self.request.user), status=201)


class ReadingListContinueView(ReadingListAccessView):
    """GET where a viewer continues a list: its first unfinished comic."""

    def get(self, *_args, **_kwargs) -> Response:
        """Return ``{continue: {pk, page} | null}``."""
        reading_list = self.get_reading_list(edit=False)
        return Response({"continue": continue_comic(self, self.request, reading_list)})


class ReadingListExportView(ReadingListAccessView):
    """
    GET a list as a file: ``?fmt=cbl|json-cbl``.

    Not ``format``: DRF reads that query parameter to choose a renderer.
    """

    def get(self, *_args, **_kwargs):
        """
        Write the list; matched entries carry their comic's ids.

        Anyone who sees a list may export it, as much of it as they see.
        """
        reading_list = self.get_reading_list(edit=False)
        shown_q = self.shown_entries_q()
        missing = self.request.GET.get("missing") in _TRUE_VALUES
        if missing:
            # Export Missing: only the issues the library lacks, to hunt for.
            shown_q &= Q(comic__isnull=True)
        fmt = self.request.GET.get("fmt", "cbl")
        if fmt not in EXPORT_FORMATS:
            reason = f"Unknown format {fmt!r}. Known: {', '.join(EXPORT_FORMATS)}."
            raise ValidationError(reason)
        token, suffix, content_type = EXPORT_FORMATS[fmt]
        try:
            text = dumps(export_document(reading_list, shown_q), token)
        except ReadingListError as exc:
            raise ValidationError(str(exc)) from exc
        response = HttpResponse(text, content_type=f"{content_type}; charset=utf-8")
        filename = export_filename(
            reading_list, f" (missing){suffix}" if missing else suffix
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

"""The admin lists table, a list's detail, and actions on lists."""

from collections import defaultdict
from types import MappingProxyType
from typing import Any, Final

from django.db.models import Count, Q
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from codex.choices.tagging import KEEP_WRITE_FORMAT, NAMED_WRITE_FORMATS
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.onlinetag.readinglists import (
    FetchRequest,
    ReadingListFetchAbortTask,
    ReadingListFetchTask,
    refresh_request,
)
from codex.librarian.scribe.readinglists.errors import (
    clear_reading_list_errors,
    get_reading_list_errors,
)
from codex.librarian.scribe.readinglists.service import (
    REMOTE_KINDS,
    copy_list,
    rank_sources,
    remove_source,
)
from codex.librarian.scribe.readinglists.tasks import (
    ReadingListRecombineTask,
    ReadingListRematchTask,
)
from codex.librarian.scribe.readinglists.write import arc_write, mark_written
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import Comic, StoryArc
from codex.models.admin import ComicboxTaggingDefaults
from codex.models.readinglist import (
    ReadingList,
    ReadingListSource,
    ReadingListSourceKind,
)
from codex.views.admin.auth import AdminAPIView

_SOURCE_LABELS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {str(value): str(label) for value, label in ReadingListSourceKind.choices}
)
# What a list is written into when the admin has no default formats.
_FALLBACK_FORMATS: Final = ("COMIC_INFO",)
_ARC_POINTER_SOURCES: Final = MappingProxyType(
    {
        "metron": ReadingListSourceKind.METRON_ARC,
        "comicvine": ReadingListSourceKind.COMICVINE_ARC,
    }
)


def source_repr(source: ReadingListSource) -> dict[str, Any]:
    """Return a source for a chip in the table and the sources panel."""
    return {
        "pk": source.pk,
        "kind": source.kind,
        "label": _SOURCE_LABELS.get(source.kind, source.kind),
        "ref": source.ref,
        "attribution": source.attribution_source,
        "attribution_url": source.attribution_url,
        "rank": source.rank,
        "ordered": source.ordered,
        "revision": source.revision,
        "fetched_at": source.fetched_at,
        "refreshable": source.kind in REMOTE_KINDS,
    }


def _arc_pointers() -> dict[str, dict[str, str]]:
    """Map arc sort names to the databases' ids for that arc."""
    pointers: defaultdict[str, dict[str, str]] = defaultdict(dict)
    rows = StoryArc.objects.filter(identifier__isnull=False).values_list(
        "sort_name", "identifier__source__name", "identifier__key"
    )
    for sort_name, source, key in rows:
        if kind := _ARC_POINTER_SOURCES.get(source):
            pointers[sort_name].setdefault(kind, key)
    return pointers


def completable_arc(sources: list[ReadingListSource], pointers) -> dict | None:
    """Return the database arc a tags list can be completed from, if any."""
    kinds = {source.kind for source in sources}
    for source in sources:
        if source.kind != ReadingListSourceKind.TAGS.value:
            continue
        for kind, key in pointers.get(source.ref, {}).items():
            if kind not in kinds:
                return {"kind": kind, "ref": key}
    return None


def _annotated_lists():
    shown = Q(entries__ignored=False)
    return (
        ReadingList.objects.select_related("user")
        .annotate(
            total=Count("entries", filter=shown, distinct=True),
            matched=Count(
                "entries", filter=shown & Q(entries__comic__isnull=False), distinct=True
            ),
            review=Count(
                "entries", filter=shown & Q(entries__needs_review=True), distinct=True
            ),
        )
        .order_by("sort_name", "pk")
    )


def list_row(reading_list, sources, pointers) -> dict[str, Any]:
    """Return a row of the admin lists table."""
    return {
        "pk": reading_list.pk,
        "name": reading_list.name,
        "list_type": reading_list.list_type,
        "sources": [source_repr(source) for source in sources],
        "total": reading_list.total,
        "matched": reading_list.matched,
        "needs_review": reading_list.review,
        "owner": reading_list.user.username if reading_list.user else None,
        "order_locked": reading_list.order_locked,
        "updated_at": reading_list.updated_at,
        "complete_from": completable_arc(sources, pointers),
    }


class AdminReadingListsView(AdminAPIView):
    """GET every reading list for the admin table."""

    def get(self, *_args, **_kwargs) -> Response:
        """Return the table rows, with sources, coverage and review counts."""
        sources: defaultdict[int, list[ReadingListSource]] = defaultdict(list)
        for source in ReadingListSource.objects.order_by("rank", "pk"):
            sources[source.reading_list_id].append(source)  # pyright: ignore[reportAttributeAccessIssue]
        pointers = _arc_pointers()
        rows = [
            list_row(reading_list, sources.get(reading_list.pk, []), pointers)
            for reading_list in _annotated_lists()
        ]
        # Not ``errors``: the envelope renderer reserves that key.
        return Response({"lists": rows, "error_count": len(get_reading_list_errors())})


def get_list(pk) -> ReadingList:
    """Return any list, for an admin."""
    reading_list = ReadingList.objects.filter(pk=pk).first()
    if reading_list is None:
        reason = "No such reading list."
        raise NotFound(reason)
    return reading_list


class AdminReadingListDetailView(AdminAPIView):
    """GET, PATCH or DELETE one list."""

    def get(self, *_args, pk: int, **_kwargs) -> Response:
        """Return a list's row and its description."""
        reading_list = _annotated_lists().filter(pk=pk).first()
        if reading_list is None:
            reason = "No such reading list."
            raise NotFound(reason)
        sources = list(
            ReadingListSource.objects.filter(reading_list=reading_list).order_by(
                "rank", "pk"
            )
        )
        row = list_row(reading_list, sources, _arc_pointers())
        row["description"] = reading_list.description
        return Response(row)

    def patch(self, *_args, pk: int, **_kwargs) -> Response:
        """Rename a list, or make it private to this admin or global again."""
        reading_list = get_list(pk)
        data = self.request.data
        edited: set[str] = set(reading_list.edited_fields or ())
        if name := str(data.get("name") or "").strip():
            reading_list.name = name
            edited.add("name")
        if "description" in data:
            reading_list.description = str(data["description"] or "")
            edited.add("description")
        if "private" in data:
            reading_list.user = self.request.user if data["private"] else None
        reading_list.edited_fields = sorted(edited)
        reading_list.save()
        return Response({"pk": reading_list.pk})

    def delete(self, *_args, pk: int, **_kwargs) -> Response:
        """Delete a list. A list from tags comes back on the next sync."""
        get_list(pk).delete()
        return Response({"deleted": True})


def refresh_requests(reading_list: ReadingList) -> list[FetchRequest]:
    """Fetch again every remote source of a list."""
    sources = ReadingListSource.objects.filter(
        reading_list=reading_list, kind__in=REMOTE_KINDS
    )
    return [refresh_request(source) for source in sources]


def complete_request(reading_list: ReadingList) -> FetchRequest | None:
    """Fetch the whole arc behind a list from tags, as a new source."""
    sources = list(ReadingListSource.objects.filter(reading_list=reading_list))
    if arc := completable_arc(sources, _arc_pointers()):
        return FetchRequest(kind=arc["kind"], ref=arc["ref"], into_pk=reading_list.pk)
    return None


def _queue_fetch(requests: list[FetchRequest]) -> None:
    if requests:
        LIBRARIAN_QUEUE.put(ReadingListFetchTask(requests=tuple(requests)))


def _refresh(reading_lists: list[ReadingList]) -> dict[str, int]:
    requests = [
        request
        for reading_list in reading_lists
        for request in refresh_requests(reading_list)
    ]
    _queue_fetch(requests)
    # Lists from tags or uploads have nothing to fetch: recombine them.
    pks = tuple(reading_list.pk for reading_list in reading_lists)
    LIBRARIAN_QUEUE.put(ReadingListRecombineTask(list_pks=pks))
    return {"queued": len(requests)}


def _complete(reading_lists: list[ReadingList]) -> dict[str, int]:
    requests = [
        request
        for reading_list in reading_lists
        if (request := complete_request(reading_list))
    ]
    _queue_fetch(requests)
    return {"queued": len(requests)}


def _rematch(reading_lists: list[ReadingList]) -> dict[str, int]:
    pks = tuple(reading_list.pk for reading_list in reading_lists)
    LIBRARIAN_QUEUE.put(ReadingListRematchTask(list_pks=pks))
    return {"queued": len(pks)}


def _recombine(reading_lists: list[ReadingList]) -> dict[str, int]:
    pks = tuple(reading_list.pk for reading_list in reading_lists)
    LIBRARIAN_QUEUE.put(ReadingListRecombineTask(list_pks=pks))
    return {"queued": len(pks)}


def _arc_write_formats() -> tuple[str, ...]:
    """Return the admin's default tag formats, keeping a comic's others."""
    defaults = ComicboxTaggingDefaults.objects.filter(pk=1).first()
    named = tuple(
        fmt
        for fmt in (defaults.default_formats if defaults else ())
        if fmt in NAMED_WRITE_FORMATS
    )
    # ``keep`` rewrites the tag formats a comic already carries instead of
    # removing the ones not named, so writing an arc never costs a tag file.
    return (*(named or _FALLBACK_FORMATS), KEEP_WRITE_FORMAT)


def _write(reading_lists: list[ReadingList]) -> dict[str, int]:
    """
    Tag each global list's matched comics with its arc, in the files.

    A personal list stays in Codex: its name never goes into shared files.
    Comics in read-only libraries are left out.
    """
    formats = _arc_write_formats()
    queued = skipped = 0
    for reading_list in reading_lists:
        if reading_list.user_id is not None:  # pyright: ignore[reportAttributeAccessIssue]
            continue
        arc = arc_write(reading_list)
        writable = frozenset(
            Comic.objects.filter(
                pk__in=arc.patches, library__read_only=False
            ).values_list("pk", flat=True)
        )
        skipped += len(arc.patches) - len(writable)
        if not writable:
            continue
        mark_written(reading_list, arc.name)
        LIBRARIAN_QUEUE.put(
            BulkTagWriteTask(
                comic_pks=writable,
                mode="additive",
                formats=formats,
                per_comic_patches={pk: arc.patches[pk] for pk in writable},
            )
        )
        queued += len(writable)
    return {"queued": queued, "skipped": skipped}


def _copy_global(reading_lists: list[ReadingList]) -> dict[str, int]:
    """
    Copy users' personal lists into new global lists, under the same name.

    The users keep their lists as they are. Global lists are skipped.
    """
    copied = 0
    for reading_list in reading_lists:
        if reading_list.user_id is None:  # pyright: ignore[reportAttributeAccessIssue]
            continue
        copy_list(reading_list, user=None, name=reading_list.name)
        copied += 1
    return {"copied": copied}


def _delete(reading_lists: list[ReadingList]) -> dict[str, int]:
    pks = [reading_list.pk for reading_list in reading_lists]
    count, _ = ReadingList.objects.filter(pk__in=pks).delete()
    return {"deleted": count}


_ACTIONS: Final = MappingProxyType(
    {
        "refresh": _refresh,
        "complete": _complete,
        "rematch": _rematch,
        "recombine": _recombine,
        "write": _write,
        "copy_global": _copy_global,
        "delete": _delete,
    }
)


def _act(action: str, reading_lists: list[ReadingList]) -> dict[str, int]:
    if (handler := _ACTIONS.get(action)) is None:
        reason = f"Unknown action {action!r}."
        raise ValidationError(reason)
    return handler(reading_lists)


class AdminReadingListActionView(AdminAPIView):
    """POST an action on one list: refresh, complete, rematch, recombine."""

    def post(self, *_args, pk: int, action: str, **_kwargs) -> Response:
        """Queue the action."""
        return Response(_act(action, [get_list(pk)]))


class AdminReadingListBulkView(AdminAPIView):
    """POST an action on several lists: ``{action, pks}``."""

    def post(self, *_args, **_kwargs) -> Response:
        """Queue the action for every list named."""
        action = str(self.request.data.get("action") or "")
        try:
            pks = [int(pk) for pk in self.request.data.get("pks") or ()]
        except (TypeError, ValueError) as exc:
            reason = "pks must be reading list pks."
            raise ValidationError(reason) from exc
        lists = list(ReadingList.objects.filter(pk__in=pks))
        return Response(_act(action, lists))


class AdminReadingListSourceView(AdminAPIView):
    """DELETE a source, recombining its list without it."""

    def delete(self, *_args, pk: int, source_pk: int, **_kwargs) -> Response:
        """Remove the source; a list left with nothing is deleted."""
        source = (
            ReadingListSource.objects.filter(pk=source_pk, reading_list_id=pk)
            .select_related("reading_list")
            .first()
        )
        if source is None:
            reason = "No such source."
            raise NotFound(reason)
        survived = remove_source(source)
        return Response({"listDeleted": not survived})


class AdminReadingListSourcesView(AdminAPIView):
    """PUT a list's source order: ``{order: [source pk, ...]}``, primary first."""

    def put(self, *_args, pk: int, **_kwargs) -> Response:
        """Rank the sources and recombine."""
        reading_list = get_list(pk)
        try:
            order = [int(spk) for spk in self.request.data.get("order") or ()]
        except (TypeError, ValueError) as exc:
            reason = "order must be source pks."
            raise ValidationError(reason) from exc
        rank_sources(reading_list, order)
        return Response({"pk": reading_list.pk})


class AdminReadingListErrorsView(AdminAPIView):
    """GET or DELETE the reading list fetch and import errors."""

    def get(self, *_args, **_kwargs) -> Response:
        """Return the recorded errors, newest first, as a bare list."""
        return Response(list(reversed(get_reading_list_errors())))

    def delete(self, *_args, **_kwargs) -> Response:
        """Forget the errors."""
        clear_reading_list_errors()
        return Response({"cleared": True})


class AdminReadingListAbortView(AdminAPIView):
    """POST: cancel the reading list fetch under way."""

    def post(self, *_args, **_kwargs) -> Response:
        """Cancel it from the librarian's routing thread."""
        LIBRARIAN_QUEUE.put(ReadingListFetchAbortTask())
        return Response({"detail": "Cancelling the reading list fetch."})

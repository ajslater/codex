"""
What a reading list is, and how much of it a viewer has.

For the details in the metadata dialog and for Continue Reading. Every
count reads the entries the viewer sees (:func:`.access.shown_entries_q`):
a missing issue counts for everyone, a comic only for those who may see it.
"""

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from comicbox.readinglists import (
    NAME_KEY,
    NEXT_KEY,
    PREVIOUS_KEY,
    SOURCE_KEY_KEY,
    SOURCE_KIND_KEY,
    SourceKind,
)
from django.db.models import Q

from codex.choices.readinglists import SOURCE_LABELS
from codex.librarian.scribe.readinglists.documents import COMICBOX_KINDS
from codex.models import Bookmark
from codex.models.readinglist import ReadingList, ReadingListEntry, ReadingListSource
from codex.views.readinglists.access import can_edit, shown_entries_q, visible_lists

_CODEX_KINDS = {comicbox: codex for codex, comicbox in COMICBOX_KINDS.items()}


def _bookmarks(request, comic_pks: Sequence[int]) -> dict[int, tuple[int, bool]]:
    """Return the viewer's ``(page, finished)`` per comic."""
    user = request.user
    if user is not None and user.is_authenticated:
        owner = Q(user=user)
    elif session_key := request.session.session_key:
        owner = Q(session_id=session_key)
    else:
        return {}
    rows = Bookmark.objects.filter(owner, comic_id__in=comic_pks).values_list(
        "comic_id", "page", "finished"
    )
    return {pk: (page or 0, bool(finished)) for pk, page, finished in rows}


def _shown_comics(acl, request, reading_list: ReadingList) -> list[int | None]:
    """Return each shown entry's comic in list order; None is a missing issue."""
    return list(
        ReadingListEntry.objects.filter(
            shown_entries_q(acl, request.user), reading_list=reading_list
        )
        .order_by("position", "pk")
        .values_list("comic_id", flat=True)
    )


def _continue_from(
    comics: Sequence[int | None], bookmarks: Mapping[int, tuple[int, bool]]
) -> dict[str, int] | None:
    """Return the first comic in list order the viewer has not finished."""
    for comic_pk in comics:
        if comic_pk is None:
            continue
        page, finished = bookmarks.get(comic_pk, (0, False))
        if not finished:
            return {"pk": comic_pk, "page": page}
    return None


def continue_comic(acl, request, reading_list: ReadingList) -> dict[str, int] | None:
    """Return where the viewer continues the list: comic and page, or None."""
    comics = _shown_comics(acl, request, reading_list)
    return _continue_from(comics, _bookmarks(request, [c for c in comics if c]))


def _by_source(lists, ref: Mapping[str, Any]) -> ReadingList | None:
    """Find a list by the database or file a list reference names."""
    kind, key = ref.get(SOURCE_KIND_KEY), ref.get(SOURCE_KEY_KEY)
    if not (kind and key):
        return None
    if kind == SourceKind.JSON_CBL.value:
        try:
            return lists.filter(uuid=UUID(str(key))).first()
        except ValueError:
            return None
    if codex_kind := _CODEX_KINDS.get(kind):
        return lists.filter(sources__kind=codex_kind, sources__ref=str(key)).first()
    return None


def _neighbour(user, ref: Any) -> dict[str, Any] | None:
    """Link the list before or after this one, when the library has it."""
    if not isinstance(ref, Mapping):
        return None
    name = str(ref.get(NAME_KEY) or "")
    lists = visible_lists(user)
    found = _by_source(lists, ref)
    if found is None and name:
        found = lists.filter(name=name).order_by("pk").first()
    if found is None:
        return {"pk": None, "name": name} if name else None
    return {"pk": found.pk, "name": name or found.name}


def _sources(reading_list: ReadingList) -> list[dict[str, str]]:
    sources = ReadingListSource.objects.filter(reading_list=reading_list).order_by(
        "rank", "pk"
    )
    return [
        {
            "kind": source.kind,
            "label": SOURCE_LABELS.get(source.kind, source.kind),
            "attribution": source.attribution_source,
            "attribution_url": source.attribution_url,
        }
        for source in sources.only(
            "kind", "attribution_source", "attribution_url", "rank"
        )
    ]


def list_details(acl, request, reading_list: ReadingList) -> dict[str, Any]:
    """Describe a list for the metadata dialog, as this viewer sees it."""
    comics = _shown_comics(acl, request, reading_list)
    present = [comic_pk for comic_pk in comics if comic_pk is not None]
    bookmarks = _bookmarks(request, present)
    extra = reading_list.extra or {}
    return {
        "pk": reading_list.pk,
        "name": reading_list.name,
        "description": reading_list.description,
        "list_type": reading_list.list_type,
        "start_year": reading_list.start_year,
        "end_year": reading_list.end_year,
        "sources": _sources(reading_list),
        "total": len(comics),
        "in_library": len(present),
        "missing": len(comics) - len(present),
        "read": sum(1 for pk in present if bookmarks.get(pk, (0, False))[1]),
        "previous": _neighbour(request.user, extra.get(PREVIOUS_KEY)),
        "next": _neighbour(request.user, extra.get(NEXT_KEY)),
        "continue": _continue_from(comics, bookmarks),
        "editable": can_edit(request.user, reading_list),
        "personal": reading_list.user_id is not None,  # pyright: ignore[reportAttributeAccessIssue]
    }

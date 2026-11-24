"""
Find, preview and import reading lists.

Search reaches Metron and the DieselTech catalog. A preview runs the real
pipeline, fetch, parse, compare and match, and writes nothing: each list
waits in the preview cache under a token until it is imported. Files, URLs
and catalog lists preview in full, because fetching them is quick; a
Metron list or a Comic Vine arc previews its header only, and is fetched
on the online-tagging thread after Import.

``fetch_url`` will fetch any host, private and loopback ones included,
which is why only admins may preview a URL.
"""

import json
from typing import Any, Final
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from comicbox.exceptions import OnlineLookupAbortedError, ReadingListError
from comicbox.readinglists import loads
from djangorestframework_camel_case.parser import CamelCaseJSONParser
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from codex.cache import reading_list_preview_cache
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.onlinetag.readinglists import (
    FetchRequest,
    ReadingListFetchTask,
    reading_list_session,
)
from codex.librarian.scribe.readinglists.documents import check_format, to_json
from codex.librarian.scribe.readinglists.matcher import ListMatcher
from codex.librarian.scribe.readinglists.service import suggest_for
from codex.librarian.scribe.readinglists.tasks import (
    ImportItem,
    ReadingListImportTask,
)
from codex.models.readinglist import (
    ReadingList,
    ReadingListSource,
    ReadingListSourceKind,
)
from codex.settings import COMICBOX_ONLINE_CONFIG
from codex.views.admin.auth import AdminAPIView
from codex.views.readinglists.access import to_pk

_PREVIEW_KEY: Final = "readinglists:preview:{}"
_PREVIEW_TTL: Final = 60 * 60
_FETCHED_NOW: Final = frozenset(
    {ReadingListSourceKind.URL, ReadingListSourceKind.CATALOG}
)
_FETCHED_LATER: Final = frozenset(
    {
        ReadingListSourceKind.METRON_LIST,
        ReadingListSourceKind.METRON_ARC,
        ReadingListSourceKind.COMICVINE_ARC,
    }
)
_MAX_UPLOAD_BYTES: Final = COMICBOX_ONLINE_CONFIG.readinglists.max_download_bytes
CREDENTIALED_URL: Final = (
    "A URL with a user name or password is not accepted:"
    " Codex keeps a source's URL, so it would store them."
)


def _without_login(url: str) -> str | None:
    """Return the URL less its user name and password, or None if it has none."""
    parts = urlsplit(url)
    if not (parts.username or parts.password):
        return None
    host = parts.hostname or ""
    if parts.port:
        host += f":{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def _imported(kind: str, refs) -> set[str]:
    return set(
        ReadingListSource.objects.filter(kind=kind, ref__in=refs).values_list(
            "ref", flat=True
        )
    )


def _metron_rows(session, query: str, curator: str) -> list[dict[str, Any]]:
    summaries = session.search_metron(name=query or None, curator=curator or None)
    imported = _imported(
        ReadingListSourceKind.METRON_LIST, [str(item.id) for item in summaries]
    )
    return [
        {
            "ref": str(item.id),
            "name": item.name,
            "list_type": item.list_type,
            "curator": item.curator or "",
            "username": item.username,
            "rating": item.rating,
            "rating_count": item.rating_count,
            "modified": item.modified,
            "private": item.private,
            "imported": str(item.id) in imported,
        }
        for item in summaries
    ]


def _catalog_rows(session, query: str) -> list[dict[str, Any]]:
    entries = session.search_catalog(query) if query else session.catalog().entries
    revisions = dict(
        ReadingListSource.objects.filter(
            kind=ReadingListSourceKind.CATALOG,
            ref__in=[entry.path for entry in entries],
        ).values_list("ref", "revision")
    )
    return [
        {
            "ref": entry.path,
            "sha": entry.sha,
            "name": entry.name,
            "publisher": entry.publisher or "",
            "category": entry.category or "",
            "curator": entry.curator or "",
            "size": entry.size,
            "imported": entry.path in revisions,
            "updated": entry.path in revisions and revisions[entry.path] != entry.sha,
        }
        for entry in entries
    ]


class AdminReadingListSearchView(AdminAPIView):
    """GET ``?source=metron|catalog&q=``: lists to import."""

    def get(self, *_args, **_kwargs) -> Response:
        """Search Metron's reading lists or the DieselTech catalog."""
        source = self.request.GET.get("source", "catalog")
        query = (self.request.GET.get("q") or "").strip()
        try:
            with reading_list_session() as session:
                if source == "metron":
                    curator = self.request.GET.get("curator", "")
                    rows = _metron_rows(session, query, curator)
                elif source == "catalog":
                    rows = _catalog_rows(session, query)
                else:
                    reason = f"Unknown source {source!r}."
                    raise ValidationError(reason)
        except (ReadingListError, OnlineLookupAbortedError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"results": rows})


def _card(
    document: dict, kind: str, ref: str, matcher: ListMatcher, warnings=()
) -> dict[str, Any]:
    """Describe a parsed list: what it is, how much of it the library has."""
    entries = document.get("entries") or []
    matches = matcher.match(entries)
    matched = sum(1 for match in matches if match.comic_pk is not None)
    sources = document.get("sources") or [{}]
    token = uuid4().hex
    reading_list_preview_cache.set(
        _PREVIEW_KEY.format(token),
        {"document": document, "kind": kind, "ref": ref},
        _PREVIEW_TTL,
    )
    names = dict(ReadingList.objects.values_list("pk", "name"))
    return {
        "token": token,
        "kind": kind,
        "ref": ref,
        "name": document.get("name") or ref,
        "curator": (sources[0] or {}).get("curator", ""),
        "list_type": document.get("list_type", ""),
        "count": len(entries),
        "matched": matched,
        "warnings": list(warnings),
        "suggestions": [
            {
                "pk": suggestion.pk,
                "name": names.get(suggestion.pk, ""),
                "verdict": suggestion.verdict,
                "combine": suggestion.combine,
                "overlap": suggestion.overlap,
            }
            for suggestion in suggest_for(document)
        ],
    }


def _error_card(kind: str, ref: str, error: str) -> dict[str, Any]:
    return {"kind": kind, "ref": ref, "name": ref, "error": error}


def _deferred_card(spec: dict) -> dict[str, Any]:
    """Describe a list fetched after Import by the header search reported."""
    return {
        "kind": spec["kind"],
        "ref": spec["ref"],
        "name": spec.get("name") or spec["ref"],
        "curator": spec.get("curator", ""),
        "list_type": spec.get("list_type", ""),
        "count": spec.get("count"),
        # Metron's own flag: a list its curator keeps private stays private.
        "private": bool(spec.get("private")),
        "deferred": True,
        "suggestions": [],
    }


def _fetched_card(session, source: dict, matcher: ListMatcher) -> dict[str, Any]:
    """Fetch one URL or catalog list now and describe it, or say why not."""
    kind, ref = source["kind"], str(source.get("ref") or "")
    if kind == ReadingListSourceKind.URL and (shown := _without_login(ref)):
        return _error_card(kind, shown, CREDENTIALED_URL)
    try:
        if kind == ReadingListSourceKind.URL:
            result = session.fetch_url(ref)
        else:
            result = session.fetch_catalog(ref, sha=source.get("sha") or None)
        check_format(result)
    except (ReadingListError, OnlineLookupAbortedError) as exc:
        return _error_card(kind, ref, str(exc))
    document = to_json(result.reading_list)
    return _card(document, kind, ref, matcher, result.warnings)


class AdminReadingListPreviewView(AdminAPIView):
    """
    POST lists to preview: uploaded ``files`` and ``sources`` to fetch.

    ``sources`` is a list of ``{kind, ref, sha?, name?, curator?}``; in a
    multipart upload it arrives as a JSON string.
    """

    parser_classes = (CamelCaseJSONParser, MultiPartParser, FormParser)

    def _sources(self) -> list[dict]:
        sources = self.request.data.get("sources") or []
        if isinstance(sources, str):
            try:
                sources = json.loads(sources)
            except ValueError as exc:
                reason = "sources must be a JSON list."
                raise ValidationError(reason) from exc
        if not isinstance(sources, list):
            reason = "sources must be a list."
            raise ValidationError(reason)
        return [source for source in sources if isinstance(source, dict)]

    def _file_cards(self, matcher: ListMatcher) -> list[dict]:
        cards = []
        for upload in self.request.FILES.getlist("files"):
            name = upload.name or "upload"
            if upload.size > _MAX_UPLOAD_BYTES:
                cards.append(_error_card("upload", name, "The file is too large."))
                continue
            try:
                result = loads(upload.read())
                check_format(result)
            except ReadingListError as exc:
                cards.append(_error_card("upload", name, str(exc)))
                continue
            document = to_json(result.reading_list)
            cards.append(
                _card(
                    document,
                    ReadingListSourceKind.UPLOAD,
                    name,
                    matcher,
                    result.warnings,
                )
            )
        return cards

    @staticmethod
    def _fetched_cards(sources: list[dict], matcher: ListMatcher) -> list[dict]:
        fetch_now = [s for s in sources if s.get("kind") in _FETCHED_NOW]
        if not fetch_now:
            return []
        with reading_list_session() as session:
            return [_fetched_card(session, source, matcher) for source in fetch_now]

    def post(self, *_args, **_kwargs) -> Response:
        """Return a card per list; nothing is saved."""
        sources = self._sources()
        # One matcher, so the library's series index is built once.
        matcher = ListMatcher()
        cards = self._file_cards(matcher)
        cards += self._fetched_cards(sources, matcher)
        cards += [
            _deferred_card(source)
            for source in sources
            if source.get("kind") in _FETCHED_LATER and source.get("ref")
        ]
        return Response({"cards": cards})


def _into(spec: dict) -> int | None:
    """Return the list an import adds to, which must exist, or None for a new one."""
    if not spec.get("into"):
        return None
    into = to_pk(spec["into"], "into")
    if not ReadingList.objects.filter(pk=into).exists():
        reason = "No such reading list to add to."
        raise ValidationError(reason)
    return into


def _item(spec: dict, user) -> tuple[ImportItem | None, FetchRequest | None]:
    """Turn one import choice into a write now or a fetch first."""
    into = _into(spec)
    owner = user.pk if spec.get("private") else None
    name = str(spec.get("name") or "")
    if token := spec.get("token"):
        cached = reading_list_preview_cache.get(_PREVIEW_KEY.format(token))
        if not cached:
            return None, None
        return (
            ImportItem(
                document=cached["document"],
                kind=cached["kind"],
                ref=cached["ref"],
                into_pk=into,
                user_pk=owner,
                name=name,
            ),
            None,
        )
    kind = str(spec.get("kind") or "")
    if kind in _FETCHED_LATER and spec.get("ref"):
        request = FetchRequest(
            kind=kind,
            ref=str(spec["ref"]),
            into_pk=into,
            user_pk=owner,
            name=name,
        )
        return None, request
    return None, None


def _split(specs, user) -> tuple[list[ImportItem], list[FetchRequest]]:
    """Sort the choices into lists to write now and lists to fetch first."""
    items, requests = [], []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        item, request = _item(spec, user)
        if item:
            items.append(item)
        if request:
            requests.append(request)
    return items, requests


class AdminReadingListImportView(AdminAPIView):
    """
    POST the admin's choices: ``items`` of ``{token | kind+ref, into, private, name}``.

    Previewed lists are written now; Metron lists and Comic Vine arcs are
    fetched first, as a background job.
    """

    def post(self, *_args, **_kwargs) -> Response:
        """Queue the writes and the fetches."""
        specs = self.request.data.get("items") or ()
        items, requests = _split(specs, self.request.user)
        if not items and not requests:
            reason = "Nothing to import: the preview may have expired."
            raise ValidationError(reason)
        if items:
            LIBRARIAN_QUEUE.put(ReadingListImportTask(items=tuple(items)))
            # A token is spent once its list is queued.
            reading_list_preview_cache.delete_many(
                [
                    _PREVIEW_KEY.format(spec["token"])
                    for spec in specs
                    if isinstance(spec, dict) and spec.get("token")
                ]
            )
        if requests:
            LIBRARIAN_QUEUE.put(ReadingListFetchTask(requests=tuple(requests)))
        return Response({"queued": len(items), "fetching": len(requests)}, status=202)

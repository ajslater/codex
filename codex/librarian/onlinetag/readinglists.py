"""
Fetch reading lists from the network on the online-tagging thread.

Fetching must not run on the scribe thread, which also runs imports and
tag writes and would stall behind a three-minute Metron list. Fetching
here also shares Metron's and Comic Vine's sessions, rate limits and
response caches with online tagging. What comes back is handed to the
scribe as a :class:`ReadingListImportTask`, which writes the rows.
"""

from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from comicbox.events import Event, ReadingListFetchProgress
from comicbox.exceptions import OnlineLookupAbortedError, ReadingListError
from comicbox.online_session import OnlineCredentials
from comicbox.readinglists import ReadingListSession
from django.db.models import Q
from django.utils.timezone import now

from codex.librarian.onlinetag.session_state import CLIENT_NAME
from codex.librarian.onlinetag.sources import build_credentials
from codex.librarian.onlinetag.tasks import OnlineTagTask
from codex.librarian.scribe.readinglists.documents import (
    ENTRIES_KEY,
    check_format,
    to_json,
)
from codex.librarian.scribe.readinglists.errors import add_reading_list_error
from codex.librarian.scribe.readinglists.service import REMOTE_KINDS
from codex.librarian.scribe.readinglists.status import ReadingListFetchStatus
from codex.librarian.scribe.readinglists.tasks import (
    ImportItem,
    ReadingListImportTask,
)
from codex.librarian.tasks import LibrarianTask
from codex.librarian.worker import WorkerStatusBase
from codex.models.admin import ComicboxTaggingDefaults
from codex.models.readinglist import ReadingListSource, ReadingListSourceKind
from codex.settings import COMICBOX_ONLINE_CONFIG

#: How long a remote source goes before the nightly janitor fetches it again.
REFRESH_AFTER: Final = timedelta(days=7)
_METRON_KINDS: Final = frozenset(
    {ReadingListSourceKind.METRON_LIST, ReadingListSourceKind.METRON_ARC}
)
# Comic Vine has no conditional request and a small hourly budget, so its
# arcs are fetched again only when an admin asks.
_SCHEDULED_KINDS: Final = REMOTE_KINDS - {ReadingListSourceKind.COMICVINE_ARC}
EMPTY_REFRESH: Final = "The list came back with no issues; the stored list is kept."


@dataclass(frozen=True)
class FetchRequest:
    """
    One list to fetch, and what to do with it.

    ``ref`` is a URL, a catalog path or a Metron or Comic Vine id. The rest
    is passed through to the import: see :class:`ImportItem`.
    """

    kind: str
    ref: str
    sha: str = ""
    if_modified_since: datetime | None = None
    into_pk: int | None = None
    user_pk: int | None = None
    name: str = ""
    source_pk: int | None = None


@dataclass
class ReadingListFetchTask(OnlineTagTask):
    """Fetch reading lists, then import them."""

    requests: tuple[FetchRequest, ...] = ()


class ReadingListFetchAbortTask(LibrarianTask):
    """
    Cancel the reading-list fetch under way.

    Not an online-tag task: the online thread is busy with the fetch, so
    the librarian cancels it from the routing thread instead of queueing.
    """


def reading_list_credentials() -> OnlineCredentials | None:
    """
    Return the admin's keys for list fetches, or None when none is set.

    The source registry's, as tagging uses. With no key comicbox falls back
    to its config, as it does for a key the credentials leave unset.
    """
    return build_credentials(ComicboxTaggingDefaults.objects.filter(pk=1).first())


def refresh_request(source: ReadingListSource) -> FetchRequest:
    """Ask for a source again, conditionally where the remote allows it."""
    since = None
    if source.kind in _METRON_KINDS:
        with suppress(ValueError):
            since = datetime.fromisoformat(source.revision)
    is_catalog = source.kind == ReadingListSourceKind.CATALOG.value
    return FetchRequest(
        kind=source.kind,
        ref=source.ref,
        sha=source.revision if is_catalog else "",
        if_modified_since=since,
        source_pk=source.pk,
    )


def scheduled_refresh_requests() -> list[FetchRequest]:
    """
    Ask again for every remote source not fetched in ``REFRESH_AFTER``.

    Metron sources wait while there is no Metron key, rather than fail
    every night.
    """
    kinds = set(_SCHEDULED_KINDS)
    credentials = reading_list_credentials()
    if credentials is None or not credentials.metron_key:
        kinds -= _METRON_KINDS
    due = Q(fetched_at__isnull=True) | Q(fetched_at__lt=now() - REFRESH_AFTER)
    sources = ReadingListSource.objects.filter(due, kind__in=kinds).order_by(
        "kind", "pk"
    )
    return [refresh_request(source) for source in sources]


def _catalog_unchanged(session: ReadingListSession, request: FetchRequest) -> bool:
    """Whether a catalog source is still the blob it was, sparing a download."""
    if request.source_pk is None or not request.sha:
        return False
    entry = session.catalog().find(request.ref, request.sha)
    return entry is not None and (entry.path, entry.sha) == (request.ref, request.sha)


def _check_not_emptied(request: FetchRequest, result) -> None:
    """Refuse a refresh that would replace a stored list with nothing."""
    if request.source_pk is not None and not result.reading_list.get(ENTRIES_KEY):
        raise ReadingListError(EMPTY_REFRESH)


def _fetch(session: ReadingListSession, request: FetchRequest):
    """Fetch one request; None when the remote list has not changed."""
    match request.kind:
        case ReadingListSourceKind.URL:
            return session.fetch_url(request.ref)
        case ReadingListSourceKind.CATALOG:
            if _catalog_unchanged(session, request):
                return None
            return session.fetch_catalog(request.ref, sha=request.sha or None)
        case ReadingListSourceKind.METRON_LIST:
            return session.fetch_metron_list(
                int(request.ref), if_modified_since=request.if_modified_since
            )
        case ReadingListSourceKind.METRON_ARC:
            return session.fetch_metron_arc(
                int(request.ref), if_modified_since=request.if_modified_since
            )
        case ReadingListSourceKind.COMICVINE_ARC:
            return session.fetch_comicvine_arc(int(request.ref))
        case _:
            reason = f"Reading lists cannot be fetched from {request.kind!r}."
            raise ReadingListError(reason)


class ReadingListFetcher(WorkerStatusBase):
    """Fetch reading lists with one comicbox session per job."""

    def __init__(self, *args, **kwargs) -> None:
        """Hold the running session so another thread can cancel it."""
        super().__init__(*args, **kwargs)
        self._session: ReadingListSession | None = None
        self._status: ReadingListFetchStatus | None = None

    def cancel(self) -> None:
        """Cancel the fetch under way, if any. Safe from any thread."""
        if self._session is not None:
            self._session.cancel()

    def _on_event(self, event: Event) -> None:
        if not isinstance(event, ReadingListFetchProgress) or self._status is None:
            return
        total = f" of {event.total}" if event.total else ""
        self._status.subtitle = f"{event.index}{total} issues"
        self.status_controller.update(self._status)

    def _item(self, request: FetchRequest, result) -> ImportItem | None:
        document = to_json(result.reading_list) if result is not None else None
        if document is None and request.source_pk is None:
            return None
        return ImportItem(
            document=document,
            kind=request.kind,
            ref=request.ref,
            into_pk=request.into_pk,
            user_pk=request.user_pk,
            name=request.name,
            source_pk=request.source_pk,
        )

    def _fetch_all(self, session, requests) -> list[ImportItem]:
        items: list[ImportItem] = []
        for request in requests:
            try:
                result = _fetch(session, request)
                if result is not None:
                    check_format(result)
                    _check_not_emptied(request, result)
            except OnlineLookupAbortedError as exc:
                self.log.warning(f"Reading list fetch stopped: {exc}")
                add_reading_list_error(request.kind, request.ref, str(exc))
                break
            except (ReadingListError, ValueError) as exc:
                self.log.warning(f"Reading list {request.kind}:{request.ref}: {exc}")
                add_reading_list_error(request.kind, request.ref, str(exc))
            else:
                if item := self._item(request, result):
                    items.append(item)
            if self._status is not None:
                self._status.increment_complete()
                self.status_controller.update(self._status)
        return items

    def fetch(self, task: ReadingListFetchTask) -> None:
        """Fetch every request, then queue the import of what arrived."""
        self._status = ReadingListFetchStatus(0, len(task.requests))
        self.status_controller.start(self._status)
        items: list[ImportItem] = []
        try:
            with ReadingListSession(
                credentials=reading_list_credentials(),
                config=COMICBOX_ONLINE_CONFIG,
                on_event=self._on_event,
                client_name=CLIENT_NAME,
            ) as session:
                self._session = session
                items = self._fetch_all(session, task.requests)
        finally:
            self._session = None
            self.status_controller.finish(self._status)
            self._status = None
        if items:
            self.librarian_queue.put(ReadingListImportTask(items=tuple(items)))


def reading_list_session(**kwargs) -> ReadingListSession:
    """Open a comicbox session on codex's cache and the admin's keys."""
    return ReadingListSession(
        credentials=reading_list_credentials(),
        config=COMICBOX_ONLINE_CONFIG,
        client_name=CLIENT_NAME,
        **kwargs,
    )

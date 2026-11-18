"""The online-thread fetcher hands fetched lists to the scribe."""

from datetime import timedelta
from threading import Lock
from typing import Final, Self
from unittest.mock import patch

from comicbox.exceptions import OnlineLookupAbortedError, ReadingListFetchError
from comicbox.readinglists import dumps, loads
from comicbox.readinglists.sources.catalog import CatalogEntry
from django.test import TestCase
from django.utils.timezone import now
from loguru import logger

from codex.librarian.onlinetag.readinglists import (
    FetchRequest,
    ReadingListFetcher,
    ReadingListFetchTask,
    scheduled_refresh_requests,
)
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.librarian.scribe.readinglists.errors import (
    clear_reading_list_errors,
    get_reading_list_errors,
)
from codex.librarian.scribe.readinglists.tasks import ReadingListImportTask
from codex.models.admin import ComicboxTaggingDefaults
from codex.models.readinglist import (
    ReadingList,
    ReadingListSource,
    ReadingListSourceKind,
)
from tests.test_reading_list_combine import _CBL

_SESSION = "codex.librarian.onlinetag.readinglists.ReadingListSession"
_PATH: Final = "Marvel/Events/Civil War.cbl"
_SHA: Final = "a" * 40


class _Queue(list):
    """Collects what the fetcher puts on the librarian queue."""

    def put(self, task) -> None:
        self.append(task)

    def __bool__(self) -> bool:
        """Truthy even when empty: workers refuse a falsy queue."""
        return True


class _FakeSession:
    """Stands in for comicbox's session: no network."""

    def __init__(self, **_kwargs) -> None:
        self.cancelled = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def cancel(self) -> None:
        self.cancelled = True

    def fetch_url(self, url: str):
        if "broken" in url:
            reason = f"{url}: HTTP 404 Not Found."
            raise ReadingListFetchError(reason)
        if "quota" in url:
            reason = "Metron's daily quota is spent."
            raise OnlineLookupAbortedError(reason)
        if url.endswith(".yaml"):
            return loads(dumps(loads(_CBL).reading_list, "yaml"))
        return loads(_CBL)

    def fetch_metron_list(self, _list_id: int, **_kwargs):
        return None

    def catalog(self, **_kwargs):
        return self

    def find(self, path: str, _sha: str | None = None):
        if path != _PATH:
            return None
        return CatalogEntry(path=_PATH, sha=_SHA, size=1)

    def fetch_catalog(self, _path: str, **_kwargs):
        return loads(_CBL)


def _url(ref: str) -> FetchRequest:
    return FetchRequest(kind=ReadingListSourceKind.URL, ref=ref)


class FetcherTests(TestCase):
    """Fetches become one import task; failures are recorded, not raised."""

    def _run(self, *requests: FetchRequest) -> list:
        queue = _Queue()
        fetcher = ReadingListFetcher(logger, queue, Lock())
        clear_reading_list_errors()
        with patch(_SESSION, _FakeSession):
            fetcher.fetch(ReadingListFetchTask(requests=requests))
        return [task for task in queue if isinstance(task, ReadingListImportTask)]

    def test_fetched_list_is_imported(self) -> None:
        """A fetched list arrives as an import item with its document."""
        (task,) = self._run(_url("https://example.invalid/cw.cbl"))
        (item,) = task.items
        assert item.kind == ReadingListSourceKind.URL
        assert len(item.document["entries"]) == 4  # noqa: PLR2004

    def test_a_failed_fetch_is_recorded_and_the_rest_go_on(self) -> None:
        """One bad URL does not stop the others."""
        (task,) = self._run(
            _url("https://example.invalid/broken.cbl"),
            _url("https://example.invalid/cw.cbl"),
        )
        assert len(task.items) == 1
        errors = get_reading_list_errors()
        assert [error["ref"] for error in errors] == [
            "https://example.invalid/broken.cbl"
        ]

    def test_a_comicbox_format_url_is_refused(self) -> None:
        """A URL serving comicbox's own YAML list is an error, not an import."""
        (task,) = self._run(
            _url("https://example.invalid/cw.yaml"),
            _url("https://example.invalid/cw.cbl"),
        )
        assert [item.ref for item in task.items] == ["https://example.invalid/cw.cbl"]
        (error,) = get_reading_list_errors()
        assert error["ref"] == "https://example.invalid/cw.yaml"

    def test_a_spent_quota_stops_the_job(self) -> None:
        """A spent quota or a cancel ends the fetch; nothing after it runs."""
        tasks = self._run(
            _url("https://example.invalid/quota.cbl"),
            _url("https://example.invalid/cw.cbl"),
        )
        assert tasks == []

    def test_an_unchanged_refresh_still_reports(self) -> None:
        """A source refresh that finds no change hands back a None document."""
        request = FetchRequest(
            kind=ReadingListSourceKind.METRON_LIST, ref="5", source_pk=1
        )
        (task,) = self._run(request)
        assert task.items[0].document is None

    def test_an_unchanged_catalog_source_is_not_downloaded(self) -> None:
        """A refresh whose blob sha still matches the catalog skips the fetch."""
        request = FetchRequest(
            kind=ReadingListSourceKind.CATALOG, ref=_PATH, sha=_SHA, source_pk=1
        )
        (task,) = self._run(request)
        assert task.items[0].document is None

    def test_a_changed_catalog_source_is_downloaded(self) -> None:
        """A new sha, or a first import that names one, fetches the list."""
        changed = FetchRequest(
            kind=ReadingListSourceKind.CATALOG, ref=_PATH, sha="b" * 40, source_pk=1
        )
        first = FetchRequest(kind=ReadingListSourceKind.CATALOG, ref=_PATH, sha=_SHA)
        (task,) = self._run(changed, first)
        assert all(item.document for item in task.items)
        assert len(task.items) == 2  # noqa: PLR2004


class ScheduledRefreshTests(TestCase):
    """The nightly janitor asks again for the remote sources due a refresh."""

    def _source(self, kind: str, ref: str, *, days: int | None) -> ReadingListSource:
        reading_list = ReadingList.objects.create(name=f"{kind} {ref}")
        fetched_at = None if days is None else now() - timedelta(days=days)
        return ReadingListSource.objects.create(
            reading_list=reading_list, kind=kind, ref=ref, fetched_at=fetched_at
        )

    def test_only_stale_remote_sources_are_due(self) -> None:
        """Week-old catalog and URL sources; never uploads, tags or Comic Vine."""
        due = self._source(ReadingListSourceKind.CATALOG, _PATH, days=8)
        never = self._source(ReadingListSourceKind.URL, "https://e.invalid", days=None)
        self._source(ReadingListSourceKind.URL, "https://e.invalid/new", days=1)
        self._source(ReadingListSourceKind.COMICVINE_ARC, "55", days=30)
        self._source(ReadingListSourceKind.UPLOAD, "cw.cbl", days=30)
        self._source(ReadingListSourceKind.TAGS, "civil war", days=30)
        requests = scheduled_refresh_requests()
        assert {request.source_pk for request in requests} == {due.pk, never.pk}

    def test_metron_sources_wait_for_a_key(self) -> None:
        """Without a Metron key its sources are skipped, not failed."""
        metron = self._source(ReadingListSourceKind.METRON_LIST, "5", days=8)
        assert scheduled_refresh_requests() == []
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"metron_key": "test-key-hush-S106"}
        )
        (request,) = scheduled_refresh_requests()
        assert request.source_pk == metron.pk

    def test_the_janitor_queues_one_fetch(self) -> None:
        """The janitor job puts one fetch task on the queue, or none."""
        queue = _Queue()
        janitor = Janitor(logger, queue, Lock(), None)
        janitor.refresh_reading_lists()
        assert queue == []
        self._source(ReadingListSourceKind.CATALOG, _PATH, days=8)
        janitor.refresh_reading_lists()
        (task,) = queue
        assert isinstance(task, ReadingListFetchTask)
        assert task.requests[0].kind == ReadingListSourceKind.CATALOG

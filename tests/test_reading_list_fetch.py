"""The online-thread fetcher hands fetched lists to the scribe."""

from threading import Lock
from typing import Self
from unittest.mock import patch

from comicbox.exceptions import OnlineLookupAbortedError, ReadingListFetchError
from comicbox.readinglists import loads
from django.test import TestCase
from loguru import logger

from codex.librarian.onlinetag.readinglists import (
    FetchRequest,
    ReadingListFetcher,
    ReadingListFetchTask,
)
from codex.librarian.scribe.readinglists.errors import (
    clear_reading_list_errors,
    get_reading_list_errors,
)
from codex.librarian.scribe.readinglists.tasks import ReadingListImportTask
from codex.models.readinglist import ReadingListSourceKind
from tests.test_reading_list_combine import _CBL

_SESSION = "codex.librarian.onlinetag.readinglists.ReadingListSession"


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
        return loads(_CBL)

    def fetch_metron_list(self, _list_id: int, **_kwargs):
        return None


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

"""Refreshing a list's sources fetches once, and never loses a stored list."""

from threading import Lock
from typing import Any, Final, override
from unittest.mock import patch

from comicbox.readinglists import loads
from django.contrib.auth.models import User
from django.test import Client
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
from codex.librarian.scribe.readinglists.service import (
    SourceSpec,
    import_document,
    refresh_source,
)
from codex.librarian.scribe.readinglists.tasks import (
    ReadingListImportTask,
    ReadingListRecombineTask,
)
from codex.models.readinglist import (
    ReadingListEntry,
    ReadingListSource,
    ReadingListSourceKind,
)
from codex.views.admin.reading_lists.table import _act
from tests.test_reading_list_combine import _document
from tests.test_reading_list_fetch import _SESSION, _FakeSession, _Queue
from tests.test_reading_lists import ReadingListFixture

_URL: Final = "https://example.invalid/cw.cbl"
_PW: Final = "test-pw-hush-S106"
_TABLE_QUEUE: Final = "codex.views.admin.reading_lists.table.LIBRARIAN_QUEUE"
_EMPTY_CBL: Final = (
    '<?xml version="1.0"?><ReadingList><Name>Civil War</Name><Books /></ReadingList>'
)


class _EmptySession(_FakeSession):
    """A remote that answers with a list of nothing."""

    @override
    def fetch_url(self, url: str):
        del url
        return loads(_EMPTY_CBL)


def _url_list():
    spec = SourceSpec(kind=ReadingListSourceKind.URL, ref=_URL, revision="r1")
    reading_list = import_document(_document(), spec)
    source = ReadingListSource.objects.get(reading_list=reading_list)
    return reading_list, source


def _with_curator(url: str) -> dict[str, Any]:
    document = _document()
    document["sources"] = [
        {"kind": "url", "revision": "r2", "curator": "CBRO", "curator_url": url}
    ]
    return document


class RefreshActionTests(ReadingListFixture):
    """The admin Refresh action fetches; the import that follows recombines."""

    def test_refresh_queues_only_the_fetch(self) -> None:
        """No recombine is queued beside the fetch."""
        reading_list, source = _url_list()
        with patch(_TABLE_QUEUE) as queue:
            result = _act("refresh", [reading_list])
        tasks = [call.args[0] for call in queue.put.call_args_list]
        assert [type(task) for task in tasks] == [ReadingListFetchTask]
        assert [request.source_pk for request in tasks[0].requests] == [source.pk]
        assert result == {"queued": 1}
        assert not any(isinstance(task, ReadingListRecombineTask) for task in tasks)


class RefreshSourceTests(ReadingListFixture):
    """A refreshed source keeps its document unless a real list came back."""

    def test_an_empty_fetch_keeps_the_stored_list(self) -> None:
        """A remote that answers with no issues does not empty the list."""
        reading_list, source = _url_list()
        assert not refresh_source(source, {})
        source.refresh_from_db()
        assert source.document
        assert len(source.document["entries"]) == 4  # noqa: PLR2004
        assert ReadingListEntry.objects.filter(reading_list=reading_list).count() == 4  # noqa: PLR2004

    def test_the_curator_link_is_refreshed(self) -> None:
        """A new curator url replaces the stored one."""
        _reading_list, source = _url_list()
        assert refresh_source(source, _with_curator("https://cbro.invalid/cw"))
        source.refresh_from_db()
        assert source.attribution_url == "https://cbro.invalid/cw"
        assert source.attribution_source == "CBRO"


class EmptyFetchTests(ReadingListFixture):
    """The fetcher reports an empty list instead of handing it on."""

    def test_an_empty_refresh_is_an_error_not_an_import(self) -> None:
        """Nothing reaches the scribe; the admin sees why."""
        _reading_list, source = _url_list()
        queue = _Queue()
        fetcher = ReadingListFetcher(logger, queue, Lock())
        clear_reading_list_errors()
        request = FetchRequest(
            kind=ReadingListSourceKind.URL, ref=_URL, source_pk=source.pk
        )
        with patch(_SESSION, _EmptySession):
            fetcher.fetch(ReadingListFetchTask(requests=(request,)))
        assert not [task for task in queue if isinstance(task, ReadingListImportTask)]
        (error,) = get_reading_list_errors()
        assert error["ref"] == _URL


class FetchOneSourceTests(ReadingListFixture):
    """Fetch again refreshes the one source asked for."""

    @staticmethod
    def _client() -> Client:
        admin = User.objects.create_user(username="admin", password=_PW, is_staff=True)
        client = Client()
        client.force_login(admin)
        return client

    def test_fetch_again_queues_that_source(self) -> None:
        """Only the chosen source is fetched."""
        reading_list, source = _url_list()
        client = self._client()
        url = f"/api/v4/admin/reading-lists/{reading_list.pk}/sources/{source.pk}"
        with patch(_TABLE_QUEUE) as queue:
            response = client.post(url)
        assert response.status_code == 200, response.content  # noqa: PLR2004
        (task,) = [call.args[0] for call in queue.put.call_args_list]
        assert isinstance(task, ReadingListFetchTask)
        assert [request.source_pk for request in task.requests] == [source.pk]

    def test_an_upload_has_nothing_to_fetch(self) -> None:
        """A source with no remote is a 400 that says why."""
        reading_list = import_document(
            _document(), SourceSpec(kind=ReadingListSourceKind.UPLOAD, ref="a.cbl")
        )
        source = ReadingListSource.objects.get(reading_list=reading_list)
        client = self._client()
        url = f"/api/v4/admin/reading-lists/{reading_list.pk}/sources/{source.pk}"
        with patch(_TABLE_QUEUE):
            response = client.post(url)
        assert response.status_code == 400  # noqa: PLR2004

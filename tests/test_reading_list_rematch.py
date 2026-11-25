"""
Lists find comics an import adds, and matching costs a few queries per job.

After an import that added comics, curated lists are matched again. The
matcher answers a whole list with a fixed number of queries, however long
it is, and the library's series index is built once per job.
"""

from pathlib import Path
from typing import Any, Final
from unittest.mock import MagicMock, patch

from cachalot.api import cachalot_disabled
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from loguru import logger

from codex.librarian.scribe.importer.init import Counts
from codex.librarian.scribe.importer.readinglists import ReadingListsImporter
from codex.librarian.scribe.readinglists import matcher as matcher_module
from codex.librarian.scribe.readinglists.matcher import ListMatcher
from codex.librarian.scribe.readinglists.tasks import ReadingListRematchTask
from codex.models import (
    Comic,
    Identifier,
    IdentifierSource,
    ReadingListSeriesMapping,
    Series,
)
from codex.models.identifier import IdentifierType
from tests.test_reading_list_combine import _CBL
from tests.test_reading_list_fetch import _Queue
from tests.test_reading_lists import ReadingListFixture

_ADMIN: Final = "/api/v4/admin/reading-lists"
_PW: Final = "test-pw-hush-S106"


def _reference(series: str, number: int, **series_extra) -> dict[str, Any]:
    return {
        "series": {"name": series, **series_extra},
        "issue": {"name": str(number)},
        "date": {"year": 2006},
    }


def _query_count(references: list[dict[str, Any]]) -> tuple[int, list]:
    # The series index is shared until the series change: build it first, so
    # each count is the entries' own cost.
    matcher_module.library_series_index()
    # cachalot would answer a repeated query from its cache and hide it.
    with cachalot_disabled(), CaptureQueriesContext(connection) as context:
        matches = ListMatcher().match(references)
    return len(context.captured_queries), matches


class ImporterRematchTests(ReadingListFixture):
    """The importer's post-phase queues a rematch when it added comics."""

    @staticmethod
    def _importer(counts: Counts) -> tuple[ReadingListsImporter, _Queue]:
        importer = ReadingListsImporter.__new__(ReadingListsImporter)
        queue = _Queue()
        importer.counts = counts
        importer.librarian_queue = queue  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[invalid-assignment]
        importer.status_controller = MagicMock()
        importer.log = logger  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[invalid-assignment]
        return importer, queue

    def test_added_comics_queue_a_rematch(self) -> None:
        """New comics may be what a list was missing."""
        importer, queue = self._importer(Counts(comic=2))
        importer.sync_reading_lists()
        assert any(isinstance(task, ReadingListRematchTask) for task in queue)

    def test_no_new_comics_no_rematch(self) -> None:
        """Deleting tags finds no list a comic."""
        importer, queue = self._importer(Counts(tags_deleted=1))
        importer.sync_reading_lists()
        assert not any(isinstance(task, ReadingListRematchTask) for task in queue)


class BatchedMatcherTests(ReadingListFixture):
    """A mapping or series-id match costs the same for one entry as for many."""

    def _amazing(self) -> Series:
        first = self.comics[0]
        series = Series.objects.create(
            name="Spindle-Man", publisher=first.publisher, imprint=first.imprint
        )
        for number in (532, 533, 534):
            path = Path(first.path).parent / f"asm{number}.cbz"
            path.touch()
            Comic.objects.create(
                library=self.library,
                path=path,
                name=f"ASM {number}",
                issue_number=number,
                publisher=first.publisher,
                imprint=first.imprint,
                series=series,
                volume=first.volume,
                size=1,
            )
        return series

    def test_mapped_entries_cost_no_query_each(self) -> None:
        """Three mapped entries take no more queries than one."""
        series = self._amazing()
        ReadingListSeriesMapping.objects.create(
            series_key="the amazing spindle man", year=1963, series=series
        )
        refs = [
            _reference("The Amazing Spindle-Man", number, start_year=1963)
            for number in (532, 533, 534)
        ]
        one, _ = _query_count(refs[:1])
        three, matches = _query_count(refs)
        assert three == one
        assert all(match.comic_pk for match in matches)

    def test_series_id_entries_cost_no_query_each(self) -> None:
        """Three series-id entries take no more queries than one."""
        source = IdentifierSource.objects.create(name="comicvine")
        identifier = Identifier.objects.create(
            source=source, id_type=IdentifierType.SERIES, key="18023"
        )
        Series.objects.filter(pk=self.comics[0].series_id).update(identifier=identifier)
        ids = {"identifiers": {"comicvine": {"key": "18023"}}}
        refs = [_reference("Guerre Civile", number, **ids) for number in (1, 2, 3)]
        one, _ = _query_count(refs[:1])
        three, matches = _query_count(refs)
        assert three == one
        assert [match.comic_pk for match in matches] == [
            comic.pk for comic in self.comics[:3]
        ]


class SeriesIndexOnceTests(ReadingListFixture):
    """A preview of several files builds the series index once."""

    def test_one_index_per_preview(self) -> None:
        """Two uploaded lists share one series index."""
        admin = User.objects.create_user(
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        client = Client()
        client.force_login(admin)
        built = []
        real = matcher_module.SeriesNameIndex

        class _Counting(real):
            def __init__(self) -> None:
                built.append(1)
                super().__init__()

        uploads = [
            SimpleUploadedFile(f"cw{n}.cbl", _CBL.encode(), "application/xml")
            for n in (1, 2)
        ]
        with patch.object(matcher_module, "SeriesNameIndex", _Counting):
            response = client.post(f"{_ADMIN}/preview", {"files": uploads})
        assert response.status_code == 200, response.content  # noqa: PLR2004
        assert len(built) == 1

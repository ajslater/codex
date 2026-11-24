"""
The backup reads each list entry's comic path, not its whole comic (C9).

A deferred field read per entry would cost a query each, so the dump's
query count must not grow with the number of entries.
"""

from cachalot.api import cachalot_disabled
from django.db import connection
from django.test.utils import CaptureQueriesContext

from codex.models import ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from codex.user_data.dump_reading_lists import dump_reading_lists
from codex.user_data.store import SidecarStore
from tests.test_reading_lists import ReadingListFixture


class DumpFieldsTests(ReadingListFixture):
    """A hand-made list, dumped with few entries and with many."""

    def _dump_queries(self) -> int:
        store = SidecarStore.in_memory()
        try:
            # Cachalot would answer a repeated query without running it.
            with cachalot_disabled(), CaptureQueriesContext(connection) as queries:
                dump_reading_lists(store)
            return len(queries)
        finally:
            store.close()

    def _add(self, reading_list: ReadingList, count: int) -> None:
        start = ReadingListEntry.objects.filter(reading_list=reading_list).count()
        ReadingListEntry.objects.bulk_create(
            ReadingListEntry(
                reading_list=reading_list,
                position=start + n,
                comic=self.comics[n % len(self.comics)],
                match_tier=ReadingListMatchTier.MANUAL,
                manual=True,
            )
            for n in range(count)
        )

    def test_queries_do_not_grow_with_entries(self) -> None:
        reading_list = ReadingList.objects.create(name="Hand Made")
        self._add(reading_list, 2)
        few = self._dump_queries()
        self._add(reading_list, 40)
        assert self._dump_queries() == few

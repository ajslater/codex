"""
A reading-list edit takes SQLite's write lock before it reads.

SQLite starts a transaction deferred. Under WAL, one that reads and then
writes after another connection has committed fails at once with
SQLITE_BUSY_SNAPSHOT ("database is locked"); the busy timeout does not
help, as the transaction's snapshot is already stale. The librarian commits
often, so each edit's transaction opens with a write. The test database is
in memory, where the error cannot happen, so this checks the cause: the
first statement of every transaction an edit opens.
"""

import json

from django.db import connection
from django.test.utils import CaptureQueriesContext

from codex.models import ReadingListEntry
from tests.test_reading_list_items_api import _LISTS, ItemsFixture

_WRITES = ("UPDATE", "INSERT", "DELETE")
_TRANSACTION_CONTROL = ("SAVEPOINT", "RELEASE", "ROLLBACK")


def _first_statements(ctx: CaptureQueriesContext) -> list[str]:
    """Return the first statement inside each transaction the request opened."""
    sql = [query["sql"] for query in ctx.captured_queries]
    firsts = []
    for index, statement in enumerate(sql):
        if not statement.startswith("SAVEPOINT"):
            continue
        rest = (s for s in sql[index + 1 :] if not s.startswith(_TRANSACTION_CONTROL))
        firsts.append(next(rest, ""))
    return firsts


class WriteLockFirstTests(ItemsFixture):
    """Every transaction of a list edit starts with a write."""

    def _assert_writes_first(self, request) -> None:
        with CaptureQueriesContext(connection) as ctx:
            response = request()
        assert response.status_code < 400, response.content  # noqa: PLR2004
        reads = [s for s in _first_statements(ctx) if not s.startswith(_WRITES)]
        assert not reads, f"transactions that read first: {reads}"

    def test_adding_and_removing_issues(self) -> None:
        """The menu PATCH and the add inside it."""
        c1, c2, c3, _ = self.comics
        self.patch_items(self.mine, {"add": {"comics": [c1.pk, c2.pk]}})
        self._assert_writes_first(
            lambda: self.patch_items(
                self.mine,
                {"add": {"comics": [c3.pk]}, "remove": {"comics": [c1.pk]}},
            )
        )

    def test_reordering(self) -> None:
        """Moving an entry."""
        c1, c2, _, _ = self.comics
        self.patch_items(self.mine, {"add": {"comics": [c1.pk, c2.pk]}})
        entry = ReadingListEntry.objects.get(reading_list=self.mine, comic=c2)
        self._assert_writes_first(
            lambda: self.client.post(
                f"{_LISTS}/{self.mine.pk}/entries/reorder",
                data=json.dumps({"entry": entry.pk, "position": 0}),
                content_type="application/json",
            )
        )

    def test_deleting_an_entry(self) -> None:
        """Removing one entry."""
        c1, c2, _, _ = self.comics
        self.patch_items(self.mine, {"add": {"comics": [c1.pk, c2.pk]}})
        entry = ReadingListEntry.objects.get(reading_list=self.mine, comic=c1)
        self._assert_writes_first(
            lambda: self.client.delete(f"{_LISTS}/{self.mine.pk}/entries/{entry.pk}")
        )

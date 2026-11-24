"""
Reading-list reads bind their comics in batches (C8).

Each of these bound one SQL variable per comic or path. Debian's SQLite
allows 250,000; a stock build allows 32,766, and past it the query fails
with "too many SQL variables": for the migration, an aborted upgrade. The
tests lower the connection's limit to a little over one batch and hand
each read twice that.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Final
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.db import connection

from codex.librarian.scribe.readinglists.matcher import _series_and_pending
from codex.librarian.scribe.readinglists.references import PK_BATCH
from codex.librarian.scribe.readinglists.write import ArcWrite
from codex.migrations._0061_shelves_to_lists import _ShelfList
from codex.models import Bookmark, ReadingList
from codex.views.admin.reading_lists.table import _write
from codex.views.browser.download import CollectionDownloadView
from codex.views.readinglists.details import _bookmarks
from tests.test_reading_lists import ReadingListFixture

# One batch and the query's own few values fit; twice the limit does not.
_LIMIT: Final = PK_BATCH + 100
# Pks no comic has, twice the limit of them.
_MANY: Final = range(10**6, 10**6 + 2 * _LIMIT)


@contextmanager
def _variable_limit(limit: int) -> Generator[None]:
    """Lower the connection's SQL variable limit, as a stock SQLite has it."""
    connection.ensure_connection()
    raw = connection.connection
    old = raw.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, limit)
    try:
        yield
    finally:
        raw.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, old)


class BoundVariableTests(ReadingListFixture):
    """More comics than the variable limit, at every read that took one each."""

    def test_list_details_bookmarks(self) -> None:
        user = User.objects.create_user(username="u", password="x")  # noqa: S106
        comic = self.comics[0]
        Bookmark.objects.create(user=user, comic=comic, page=3)
        request = SimpleNamespace(user=user)
        with _variable_limit(_LIMIT):
            rows = _bookmarks(request, [comic.pk, *_MANY])
        assert rows[comic.pk] == (3, False)

    def test_the_matchers_pending_check(self) -> None:
        comic = self.comics[0]
        with _variable_limit(_LIMIT):
            series_of, pending = _series_and_pending([comic.pk, *_MANY])
        assert series_of[comic.pk] == comic.series_id
        assert not pending

    def test_write_to_files(self) -> None:
        reading_list = ReadingList.objects.create(name="Huge")
        patches = {pk: {} for pk in [self.comics[0].pk, *_MANY]}
        arc = ArcWrite(name="Huge", patches=patches)
        with (
            patch("codex.views.admin.reading_lists.table.arc_write", return_value=arc),
            patch("codex.views.admin.reading_lists.table.LIBRARIAN_QUEUE"),
            _variable_limit(_LIMIT),
        ):
            counts = _write([reading_list])
        assert counts["skipped"] == len(patches) - 1

    def test_a_lists_download_order(self) -> None:
        reading_list = ReadingList.objects.create(name="Huge")
        view = CollectionDownloadView()
        view.kwargs = {"collection": "arcs", "pks": (reading_list.pk,)}
        paths = tuple(f"/comics/{n}.cbz" for n in _MANY)
        with _variable_limit(_LIMIT):
            assert view._list_members(paths) is None  # noqa: SLF001

    def test_the_shelves_migration(self) -> None:
        reading_list = ReadingList.objects.create(name="Shelf")
        items = [("comics", pk) for pk in [self.comics[0].pk, *_MANY]]
        shelf = _ShelfList(apps, reading_list, items)
        with _variable_limit(_LIMIT):
            shelf.build()
        assert [pk for kind, pk, _ in shelf.rows if kind == "manual"] == [
            self.comics[0].pk
        ]

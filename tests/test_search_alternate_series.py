"""
Alternate series names are searchable.

comicbox ``reprints`` become :class:`codex.models.named.Reprint` rows and
are indexed into a dedicated ``ComicFTS.alternate_series`` column rather
than being folded into ``series`` — a ``series:`` token has to keep
meaning the canonical series.

Two independent code paths fill that column: the importer builds FTS
entries inline, and :class:`SearchIndexerSync` rebuilds them from the
database. Each keeps its own registry of FTS columns and drops values
*silently* when the registries disagree (the historical credits /
sources / story_arcs bug documented in ``scribe/search/sync.py``), so
both are asserted here end to end.
"""

from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from threading import Event, Lock
from typing import Final, override
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.test import Client
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.search.sync import SearchIndexerSync
from codex.models import Comic
from codex.models.comic import ComicFTS
from tests.importer.test_basic import PATH, BaseTestImporter, run_full_import

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
# ``tests/files/comicbox-2-example.cbz`` carries two MetronInfo
# alternate names. The second has only a ``series.sort_name``.
_ALTERNATE_SERIES: Final = "Capitan Sciencia,Kapitän Wissenschaft"
# Comfortably past any index watermark the run just wrote.
_FUTURE: Final = datetime(2100, 1, 1, tzinfo=UTC)


class AlternateSeriesSearchTestCase(BaseTestImporter):
    """Import the example fixture, then find it by its alternate names."""

    @override
    def setUp(self) -> None:
        super().setUp()
        run_full_import(self.importer)
        self.comic = Comic.objects.get(path=PATH)
        self._create_sibling()
        user = User.objects.create_user(
            username="alt_series_search_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)

    def _create_sibling(self) -> None:
        """
        Add a reprint-less comic to the same series.

        Without it every positive assertion below would also pass when
        the search filter is dropped entirely — the single imported
        comic is the whole result set either way.
        """
        path = Path(PATH).with_name("sibling.cbz")
        path.touch()
        Comic.objects.create(
            library=self.comic.library,
            path=path,
            issue_number=2,
            name="Sibling",
            publisher=self.comic.publisher,
            imprint=self.comic.imprint,
            series=self.comic.series,
            volume=self.comic.volume,
            size=1,
            page_count=1,
        )

    @staticmethod
    def _sync(*, rebuild: bool) -> None:
        indexer = SearchIndexerSync(logger, LIBRARIAN_QUEUE, Lock(), Event())
        indexer.update_search_index(rebuild=rebuild)

    def _alternate_series_column(self) -> str:
        return ComicFTS.objects.get(comic_id=self.comic.pk).alternate_series

    def _search_book_pks(self, query: str) -> list[int]:
        """Browse the comic's series with a search query and return book pks."""
        params = urlencode({"page": 1, "q": query})
        url = f"/api/v4/browse/series/{self.comic.series.pk}?{params}"
        response = self.client.get(url)
        assert response.status_code == HTTPStatus.OK, response.content
        return [book["pk"] for book in response.json()["data"]["books"]]

    def test_import_indexes_alternate_series(self) -> None:
        """The importer writes reprint series names to their own FTS column."""
        assert self._alternate_series_column() == _ALTERNATE_SERIES

    def test_unqualified_search_finds_alternate_series(self) -> None:
        """A bare token matches every FTS column, alternate names included."""
        assert self._search_book_pks("Wissenschaft") == [self.comic.pk]
        assert self._search_book_pks("Sciencia") == [self.comic.pk]
        assert self._search_book_pks("Zzyzx") == []

    def test_field_alias_search_finds_alternate_series(self) -> None:
        """Every registered alias resolves to the alternate_series column."""
        for alias in ("alternate_series", "alt_series", "alternateseries", "reprints"):
            assert self._search_book_pks(f"{alias}:Sciencia") == [self.comic.pk], alias
            # An unregistered column is silently discarded from the query
            # rather than erroring, so the miss has to be asserted too.
            assert self._search_book_pks(f"{alias}:Zzyzx") == [], alias

    def test_series_token_excludes_alternate_series(self) -> None:
        """The canonical series column stays free of alternate names."""
        assert self._search_book_pks("series:Sciencia") == []
        assert self._search_book_pks("series:Captain") == [self.comic.pk]

    def test_search_index_sync_populates_alternate_series(self) -> None:
        """A full index rebuild fills the column the importer filled."""
        self._sync(rebuild=True)
        assert self._alternate_series_column() == _ALTERNATE_SERIES
        assert self._search_book_pks("alt_series:Wissenschaft") == [self.comic.pk]

    def test_search_index_sync_updates_alternate_series(self) -> None:
        """An incremental sync carries the column through ``bulk_update``."""
        self._sync(rebuild=True)
        self.comic.reprints.clear()
        # ``updated_at`` is auto_now, so ``.update()`` is the only way to
        # push the comic past the index watermark without a save().
        Comic.objects.filter(pk=self.comic.pk).update(updated_at=_FUTURE)
        self._sync(rebuild=False)
        assert self._alternate_series_column() == ""

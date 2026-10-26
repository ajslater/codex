"""
Series start year, end year, status and summary are searchable.

The years and status are ORM columns reached across the series FK, like
``year:``. The summary is indexed into its own ``ComicFTS.series_summary``
column so bare search terms find it.

Three code paths write that column: the importer builds FTS entries inline
for the comics it links, its foreign-key re-sync rewrites every comic of a
series whose summary changed (the inline path skips comics whose series
link didn't change), and :class:`SearchIndexerSync` rebuilds it from the
database. Each is asserted here.
"""

import shutil
import zipfile
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from threading import Event, Lock
from typing import Final, override
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.search.sync import SearchIndexerSync
from codex.models import Comic, Publisher, Series
from codex.models.comic import ComicFTS
from codex.models.library import Library
from codex.startup import codex_init
from tests.importer.test_basic import run_full_import
from tests.tmp_dirs import tmp_dir

TMP_DIR: Final = tmp_dir(Path(__file__).stem)
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_ALPHA_SUMMARY: Final = "A rodeo of heroes."
# Comfortably past any index watermark the run just wrote.
_FUTURE: Final = datetime(2100, 1, 1, tzinfo=UTC)


def _yaml(series: str, extra: str = "") -> str:
    return f"""comicbox:
  publisher:
    name: P
  series:
    name: {series}
{extra}"""


_ALPHA_YAML: Final = _yaml(
    "Alpha",
    f"""    start_year: 1963
    end_year: 1996
    status: completed
    summary: {_ALPHA_SUMMARY}
""",
)
_BETA_YAML: Final = _yaml("Beta", "    start_year: 2001\n")


class _SeriesSearchTestCase(TestCase):
    """Import comics from archives carrying series attributes."""

    @override
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cache.clear()
        codex_init()

    @override
    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(TMP_DIR, ignore_errors=True)
        finally:
            super().tearDownClass()

    @override
    def setUp(self):
        cache.clear()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=TMP_DIR)  # pyright: ignore[reportUninitializedInstanceVariable]
        user = User.objects.create_user(
            username="series_search_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self):
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        cache.clear()

    @staticmethod
    def _write(name: str, yaml: str) -> str:
        path = TMP_DIR / name
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("comicbox.yaml", yaml)
            zf.writestr("page1.jpg", b"\xff\xd8\xff\xe0not-a-real-jpeg")
        return str(path)

    def _import(self, *paths: str) -> None:
        # A same-size rewrite within the same second looks unchanged to the
        # mtime prefilter, so always re-read.
        task = ImportTask(
            library_id=self.library.pk,
            files_modified=frozenset(paths),
            check_metadata_mtime=False,
        )
        run_full_import(ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event()))

    @staticmethod
    def _series_summary_column(path: str) -> str:
        return ComicFTS.objects.get(comic__path=path).series_summary

    def _browse(self, url: str, query: str) -> dict:
        params = urlencode({"page": 1, "q": query})
        response = self.client.get(f"{url}?{params}")
        assert response.status_code == HTTPStatus.OK, response.content
        return response.json()["data"]


class SeriesFieldsSearchTestCase(_SeriesSearchTestCase):
    """Two series, one with every attribute set and one with only a start."""

    @override
    def setUp(self):
        super().setUp()
        self.alpha_path = self._write("alpha.cbz", _ALPHA_YAML)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.beta_path = self._write("beta.cbz", _BETA_YAML)  # pyright: ignore[reportUninitializedInstanceVariable]
        self._import(self.alpha_path, self.beta_path)
        self.publisher = Publisher.objects.get(name="P")  # pyright: ignore[reportUninitializedInstanceVariable]

    def _series_names(self, query: str) -> list[str]:
        """Search the publisher's series cards: the ``series__`` strip."""
        body = self._browse(f"/api/v4/browse/publishers/{self.publisher.pk}", query)
        return sorted(card["name"] for card in body["collections"])

    def _publisher_names(self, query: str) -> list[str]:
        """Search the publisher cards: the ``comic__`` prefix."""
        body = self._browse("/api/v4/browse/publishers", query)
        return [card["name"] for card in body["collections"]]

    def _book_pks(self, path: str, query: str) -> list[int]:
        """Search the comic's series' comics: no prefix."""
        comic = Comic.objects.get(path=path)
        body = self._browse(f"/api/v4/browse/series/{comic.series_id}", query)  # pyright: ignore[reportAttributeAccessIssue]
        return [book["pk"] for book in body["books"]]

    def test_import_indexes_series_summary(self) -> None:
        """The inline path writes each comic's series summary, blank or not."""
        assert self._series_summary_column(self.alpha_path) == _ALPHA_SUMMARY
        assert self._series_summary_column(self.beta_path) == ""

    def test_bare_term_finds_series_summary(self) -> None:
        """A bare token matches the series summary column."""
        assert self._series_names("rodeo") == ["Alpha"]
        assert self._series_names("Zzyzx") == []

    def test_field_aliases_find_series_summary(self) -> None:
        """Every alias resolves to the series summary, not the comic's."""
        for alias in ("series_summary", "series_desc", "series_description"):
            assert self._series_names(f"{alias}:rodeo") == ["Alpha"], alias
        assert self._series_names("summary:rodeo") == []

    def test_series_columns(self) -> None:
        """Years and status search like ``year:`` across the series FK."""
        hits = (
            "start_year:1963",
            "start_year:1960..1970",
            "end_year:<2000",
            "status:completed",
            "status:comp*",
        )
        for query in hits:
            assert self._series_names(query) == ["Alpha"], query
        assert self._series_names("start_year:>1990") == ["Beta"]
        assert self._series_names("status:ongoing") == []

    def test_series_columns_on_publishers(self) -> None:
        """Collection browses above the series reach it through its comics."""
        assert self._publisher_names("start_year:1963") == ["P"]
        assert self._publisher_names("status:completed") == ["P"]
        assert self._publisher_names("start_year:1900") == []

    def test_series_columns_on_comics(self) -> None:
        """A series' comics match on their own series' attributes."""
        alpha_pk = Comic.objects.get(path=self.alpha_path).pk
        beta_pk = Comic.objects.get(path=self.beta_path).pk
        assert self._book_pks(self.alpha_path, "status:completed") == [alpha_pk]
        assert self._book_pks(self.beta_path, "status:completed") == []
        assert self._book_pks(self.beta_path, "start_year:2001") == [beta_pk]

    def test_search_index_sync_populates_series_summary(self) -> None:
        """A full rebuild fills the column; an incremental sync updates it."""
        indexer = SearchIndexerSync(logger, LIBRARIAN_QUEUE, Lock(), Event())
        indexer.update_search_index(rebuild=True)
        assert self._series_summary_column(self.alpha_path) == _ALPHA_SUMMARY
        assert self._series_names("rodeo") == ["Alpha"]

        Series.objects.filter(name="Alpha").update(summary="A lasso.")
        # ``updated_at`` is auto_now, so ``.update()`` is the only way to
        # push the comic past the index watermark without a save().
        Comic.objects.filter(path=self.alpha_path).update(updated_at=_FUTURE)
        indexer.update_search_index(rebuild=False)
        assert self._series_summary_column(self.alpha_path) == "A lasso."


class SeriesSummaryResyncTestCase(_SeriesSearchTestCase):
    """A summary change re-indexes comics the import didn't touch."""

    def test_summary_change_reindexes_series_comics(self) -> None:
        """Re-importing one comic updates its sibling's index row too."""
        a_path = self._write("a.cbz", _yaml("Shared", "    summary: one\n"))
        b_path = self._write("b.cbz", _yaml("Shared"))
        self._import(a_path, b_path)
        assert self._series_summary_column(b_path) == "one"

        self._write("a.cbz", _yaml("Shared", "    summary: two\n"))
        self._import(a_path)
        assert Series.objects.get(name="Shared").summary == "two"
        assert self._series_summary_column(a_path) == "two"
        assert self._series_summary_column(b_path) == "two"

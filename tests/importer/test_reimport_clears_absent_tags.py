"""
A re-import replaces a comic's tags with the file's, absent ones included.

The importer updated only the fields the file's fresh tags held, so a tag
the file no longer had kept its old value in the database: a summary
cleared in Codex's own tag editor stayed in the metadata dialog and in
search, and a comic imported under comicbox 5.6.1 kept the stale issue
suffix and the invented month or day 5.6.2 no longer reads. Now a
re-import that read the file's tags leaves the comic as a fresh import of
that file would.

A re-import that read no tags (metadata import off, or comicbox found the
file unchanged) changes none of them.

The search index had the same gap for links: a re-import that dropped
some of a comic's genres or identifiers kept the dropped ones indexed.
"""

import shutil
import zipfile
from pathlib import Path
from threading import Event, Lock
from types import MappingProxyType
from typing import Final, override
from unittest.mock import MagicMock

from django.core.cache import cache
from django.test import TestCase
from loguru import logger

from codex.choices.admin import AdminFlagChoices
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.models import AdminFlag, Comic, Library
from codex.models.comic import ComicFTS
from codex.startup import codex_init
from tests.tmp_dirs import tmp_dir

TMP_DIR: Final = tmp_dir(Path(__file__).stem)
_PAGE: Final = b"\xff\xd8\xff\xe0not-a-real-jpeg"
_COLLECTIONS: Final = """comicbox:
  publisher:
    name: P
  imprint:
    name: I
  series:
    name: S
  volume:
    number: 2001
"""
_RICH: Final = (
    _COLLECTIONS
    + """  title: A Title
  collection_title: A Collection
  issue:
    name: 5a
  alternative_issue:
    name: 7b
  date:
    year: 2006
    month: 7
    day: 9
  summary: A summary
  review: A review
  notes: Some notes
  community_rating:
    average_rating: 4.5
    rating_count: 12
  manga: "Yes"
  manga_volume: 1-3
  monochrome: true
  reading_direction: rtl
  urls:
    - https://example.com/c
  language: en
  country: US
  age_rating: Teen
  original_format: Hardcover
  scan_info: scans
  tagger: someone
  genres:
    Drama: {}
  characters:
    Alpha: {}
  protagonist: Alpha
  credits:
    Joe:
      roles:
        Writer: {}
  arcs:
    Saga:
      number: 1
  identifiers:
    comicvine:
      key: "145269"
  locations:
    Moon: {}
  reprints:
    - name: Other Edition
      language: es
  series_groups:
    - Group
  tags:
    t: {}
  teams:
    Squad: {}
  universes:
    Earth Two: {}
"""
)
# Every field a comic's tags set, as a fresh import of a file without
# them leaves it: single values, lookups and lists.
_SCALAR_FIELDS: Final = (
    "name",
    "sort_name",
    "collection_title",
    "issue_number",
    "issue_suffix",
    "alternative_issue_number",
    "alternative_issue_suffix",
    "year",
    "month",
    "day",
    "date",
    "decade",
    "summary",
    "review",
    "notes",
    "community_rating",
    "community_rating_count",
    "manga",
    "manga_volume",
    "monochrome",
    "reading_direction",
    "urls",
    "language_id",
    "country_id",
    "age_rating_id",
    "original_format_id",
    "scan_info_id",
    "tagger_id",
    "main_character_id",
    "main_team_id",
)
_M2M_FIELDS: Final = (
    "characters",
    "credits",
    "genres",
    "identifiers",
    "locations",
    "reprints",
    "series_groups",
    "stories",
    "story_arc_numbers",
    "tags",
    "teams",
    "universes",
)
# What names a linked row, for the m2ms whose rows have no name.
_M2M_NAME_PATHS: Final = MappingProxyType(
    {
        "credits": "person__name",
        "identifiers": "key",
        "reprints": "series_name",
        "story_arc_numbers": "story_arc__name",
    }
)
_FTS_IGNORE_FIELDS: Final = frozenset({"comic", "created_at", "updated_at"})


def _tags(*lines: str) -> str:
    return "\n".join((_COLLECTIONS.rstrip("\n"), *lines, ""))


class TestReimportClearsAbsentTags(TestCase):
    """After a tag-reading re-import the comic matches the file."""

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

    @override
    def tearDown(self):
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        cache.clear()

    @staticmethod
    def _write(name: str, tags: str) -> str:
        path = TMP_DIR / name
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("comicbox.yaml", tags)
            zf.writestr("page0.jpg", _PAGE)
        return str(path)

    def _import(self, **task_kwargs) -> None:
        task = ImportTask(library_id=self.library.pk, **task_kwargs)
        importer = ComicImporter(task, logger, MagicMock(), Lock(), Event())
        assert importer._run_per_comic_phases_chunked()  # noqa: SLF001
        importer.fail_imports()
        importer.delete()
        importer.full_text_search()
        importer.finish()

    def _scan(self, path: str) -> None:
        self._import(files_created=frozenset({path}))

    def _force(self, path: str) -> None:
        """Re-read the way Force Update and the tag writer's re-read do."""
        self._import(
            files_modified=frozenset({path}),
            force_import_metadata=True,
            check_metadata_mtime=False,
        )

    @staticmethod
    def _snapshot(path: str) -> MappingProxyType:
        comic = Comic.objects.get(path=path)
        values = {field: getattr(comic, field) for field in _SCALAR_FIELDS}
        for field in _M2M_FIELDS:
            name_path = _M2M_NAME_PATHS.get(field, "name")
            values[field] = sorted(
                getattr(comic, field).values_list(name_path, flat=True)
            )
        return MappingProxyType(values)

    @staticmethod
    def _search_entry(path: str) -> MappingProxyType:
        """Return the comic's search index row, timestamps aside."""
        comic_fts = ComicFTS.objects.get(comic_id=Comic.objects.get(path=path).pk)
        return MappingProxyType(
            {
                field.name: getattr(comic_fts, field.name)
                for field in ComicFTS._meta.concrete_fields
                if field.name not in _FTS_IGNORE_FIELDS
            }
        )

    def test_a_reimport_with_tags_removed_matches_a_fresh_import(self) -> None:
        """Remove every optional tag from a file; the comic loses them all."""
        path = self._write("rich.cbz", _RICH)
        self._scan(path)
        rich = self._snapshot(path)
        assert rich["summary"] == "A summary"
        assert rich["main_character_id"] is not None
        assert all(rich[field] for field in _M2M_FIELDS), rich
        assert self._search_entry(path)["genres"] == "Drama"

        self._write("rich.cbz", _COLLECTIONS)
        self._force(path)

        fresh = self._write("fresh.cbz", _COLLECTIONS)
        self._scan(fresh)
        assert self._snapshot(path) == self._snapshot(fresh)
        assert self._search_entry(path) == self._search_entry(fresh)

    def test_minus_one_stored_by_5_6_1_drops_its_suffix(self) -> None:
        """A row stored as (NULL, "-1") re-imports as (-1, ""), not "#-1-1"."""
        path = self._write("minus.cbz", _tags("  issue:", "    name: '-1'"))
        self._scan(path)
        # What comicbox 5.6.1 stored for the same file.
        Comic.objects.filter(path=path).update(issue_number=None, issue_suffix="-1")

        self._force(path)

        comic = Comic.objects.get(path=path)
        assert (comic.issue_number, comic.issue_suffix) == (-1, "")

    def test_a_partial_date_drops_an_invented_day(self) -> None:
        """A row 5.6.1 padded to 2006-07-18 re-imports as 2006-07."""
        path = self._write(
            "partial.cbz", _tags("  date:", "    year: 2006", "    month: 7")
        )
        self._scan(path)
        Comic.objects.filter(path=path).update(day=18)

        self._force(path)

        comic = Comic.objects.get(path=path)
        assert (comic.year, comic.month, comic.day) == (2006, 7, None)

    def test_a_reimport_that_reads_no_tags_keeps_them(self) -> None:
        """With metadata import off nothing is read, so nothing is cleared."""
        path = self._write("kept.cbz", _RICH)
        self._scan(path)
        rich = self._snapshot(path)
        rich_entry = self._search_entry(path)
        AdminFlag.objects.filter(key=AdminFlagChoices.IMPORT_METADATA.value).update(
            on=False
        )
        self._write("kept.cbz", _COLLECTIONS)

        self._import(files_modified=frozenset({path}), check_metadata_mtime=False)

        assert self._snapshot(path) == rich
        assert self._search_entry(path) == rich_entry

    def test_a_partial_removal_leaves_the_search_entry_its_kept_links(self) -> None:
        """Removing some genres and identifiers unindexes just those."""
        path = self._write(
            "partial-links.cbz",
            _tags(
                *("  genres:", "    Drama: {}", "    Comedy: {}"),
                *("  identifiers:", "    comicvine:", "      key: '1'"),
                *("    metron:", "      key: '2'"),
            ),
        )
        self._scan(path)
        entry = self._search_entry(path)
        assert entry["genres"] == "Comedy,Drama"
        assert entry["sources"] == "Comic Vine,Metron,comicvine,metron"
        kept = _tags(
            *("  genres:", "    Drama: {}"),
            *("  identifiers:", "    metron:", "      key: '2'"),
        )

        self._write("partial-links.cbz", kept)
        self._force(path)

        fresh = self._write("fresh-links.cbz", kept)
        self._scan(fresh)
        assert self._snapshot(path)["genres"] == ["Drama"]
        assert self._search_entry(path) == self._search_entry(fresh)

"""
Issue #0 imports as the number 0.

The importer flattened the issue number only when it was truthy, so a
number of 0 was dropped and issue #0 imported as no number: it sorted
with the unnumbered issues instead of first.
"""

import shutil
import zipfile
from pathlib import Path
from threading import Event, Lock
from typing import Final, override
from unittest.mock import MagicMock

from django.core.cache import cache
from django.test import TestCase
from loguru import logger

from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.models import Comic, Library
from codex.startup import codex_init
from tests.tmp_dirs import tmp_dir

TMP_DIR: Final = tmp_dir(Path(__file__).stem)
_PAGE: Final = b"\xff\xd8\xff\xe0not-a-real-jpeg"
_TAGS: Final = "comicbox:\n  series:\n    name: S\n  issue:\n    name: '0'\n"


class TestImportIssueZero(TestCase):
    """A comic tagged issue 0 stores issue_number 0."""

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

    def test_issue_zero_is_kept(self) -> None:
        """Issue 0 is a number, not an absent one."""
        path = TMP_DIR / "zero.cbz"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("comicbox.yaml", _TAGS)
            zf.writestr("page0.jpg", _PAGE)
        task = ImportTask(
            library_id=self.library.pk, files_created=frozenset({str(path)})
        )
        importer = ComicImporter(task, logger, MagicMock(), Lock(), Event())
        assert importer._run_per_comic_phases_chunked()  # noqa: SLF001
        importer.fail_imports()
        importer.delete()
        importer.full_text_search()
        importer.finish()

        comic = Comic.objects.get(path=str(path))
        assert comic.issue_number == 0

"""
Every comic's search row carries its universes' designations.

A full ``SearchIndexerSync`` rebuild indexes each universe as its
designation and its name. The importer writes the same row inline, so a
comic must get the designation whether its universe was created in this
import, already existed, was kept from an earlier import, or was linked in
a later chunk of a chunked import.
"""

import shutil
import zipfile
from pathlib import Path
from threading import Event, Lock
from typing import Final, override
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.models.comic import ComicFTS
from codex.models.library import Library
from codex.startup import codex_init
from tests.importer.test_basic import run_full_import
from tests.tmp_dirs import tmp_dir

TMP_DIR: Final = tmp_dir(Path(__file__).stem)
_ALPHA: Final = ("Alpha", "1")
_BETA: Final = ("Beta", "2")


def _yaml(*universes: tuple[str, str]) -> str:
    lines = [
        "comicbox:",
        "  publisher:",
        "    name: P",
        "  series:",
        "    name: S",
        "  universes:",
    ]
    for name, designation in universes:
        lines += [f"    {name}:", f"      designation: '{designation}'"]
    return "\n".join(lines) + "\n"


class TestUniverseFTSDesignations(TestCase):
    """The importer indexes universe designations on every linked comic."""

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
    def _write(name: str, *universes: tuple[str, str]) -> str:
        path = TMP_DIR / f"{name}.cbz"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("comicbox.yaml", _yaml(*universes))
            zf.writestr("page1.jpg", b"\xff\xd8\xff\xe0not-a-real-jpeg")
        return str(path)

    def _importer(self, *paths: str) -> ComicImporter:
        # A same-size rewrite within the same second looks unchanged to the
        # mtime prefilter, so always re-read.
        task = ImportTask(
            library_id=self.library.pk,
            files_modified=frozenset(paths),
            check_metadata_mtime=False,
        )
        return ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())

    def _import(self, *paths: str) -> None:
        run_full_import(self._importer(*paths))

    @staticmethod
    def _universes_column(path: str) -> str:
        return ComicFTS.objects.get(comic__path=path).universes

    def test_new_universe_shared_in_one_batch(self) -> None:
        """Every comic linking a newly created universe gets its designation."""
        paths = (self._write("a1", _ALPHA), self._write("a2", _ALPHA))
        self._import(*paths)
        for path in paths:
            assert self._universes_column(path) == "1,Alpha", path

    def test_several_universes_on_one_comic(self) -> None:
        """A comic with two new universes gets both designations."""
        path = self._write("ab", _ALPHA, _BETA)
        self._import(path)
        assert self._universes_column(path) == "1,2,Alpha,Beta"

    def test_new_link_to_an_existing_universe(self) -> None:
        """A comic linking a universe an earlier import created gets it too."""
        self._import(self._write("a1", _ALPHA))
        path = self._write("a2", _ALPHA)
        self._import(path)
        assert self._universes_column(path) == "1,Alpha"

    def test_kept_universe_keeps_its_designation(self) -> None:
        """Adding a universe to a comic keeps the old one's designation."""
        path = self._write("a1", _ALPHA)
        self._import(path)
        self._write("a1", _ALPHA, _BETA)
        self._import(path)
        assert self._universes_column(path) == "1,2,Alpha,Beta"

    def test_later_chunk_links_an_earlier_chunks_universe(self) -> None:
        """A comic in a later chunk gets a universe an earlier chunk created."""
        paths = (self._write("a1", _ALPHA), self._write("a2", _ALPHA))
        importer = self._importer(*paths)
        with patch.object(
            ComicImporter, "_compute_chunk_size", staticmethod(lambda: 1)
        ):
            assert importer._run_per_comic_phases_chunked()  # noqa: SLF001
        importer.fail_imports()
        importer.delete()
        importer.full_text_search()
        for path in paths:
            assert self._universes_column(path) == "1,Alpha", path

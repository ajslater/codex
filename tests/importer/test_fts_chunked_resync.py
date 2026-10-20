"""
An import's foreign-key search re-sync covers every per-comic chunk.

``read → query → create_and_update → link`` runs once per chunk of paths,
but the search index is synced once afterwards. The tags each chunk
updated must accumulate until then, or only the last chunk's comics would
be re-indexed.
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


def _yaml(universe: str, designation: str) -> str:
    return f"""comicbox:
  publisher:
    name: P
  series:
    name: S
  universes:
    {universe}:
      designation: '{designation}'
"""


class TestFTSChunkedResync(TestCase):
    """Two chunks each update a universe; both universes' comics re-index."""

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
    def _write(name: str, yaml: str) -> str:
        path = TMP_DIR / name
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("comicbox.yaml", yaml)
            zf.writestr("page1.jpg", b"\xff\xd8\xff\xe0not-a-real-jpeg")
        return str(path)

    def _importer(self, paths) -> ComicImporter:
        # A same-size rewrite within the same second looks unchanged to the
        # mtime prefilter, so always re-read.
        task = ImportTask(
            library_id=self.library.pk,
            files_modified=frozenset(paths),
            check_metadata_mtime=False,
        )
        return ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())

    @staticmethod
    def _universes_column(path: str) -> str:
        return ComicFTS.objects.get(comic__path=path).universes

    def test_every_chunk_reindexes_its_universes(self) -> None:
        """Siblings outside the import pick up both chunks' designations."""
        paths = {
            name: self._write(f"{name}.cbz", _yaml(universe, designation))
            for name, universe, designation in (
                ("a1", "Alpha", "1"),
                ("a2", "Alpha", "1"),
                ("b1", "Beta", "2"),
                ("b2", "Beta", "2"),
            )
        }
        run_full_import(self._importer(paths.values()))

        # Re-import one comic per universe with a new designation, one
        # comic per chunk. a2 and b2 are re-indexed only by the re-sync.
        self._write("a1.cbz", _yaml("Alpha", "11"))
        self._write("b1.cbz", _yaml("Beta", "22"))
        importer = self._importer((paths["a1"], paths["b1"]))
        with patch.object(
            ComicImporter, "_compute_chunk_size", staticmethod(lambda: 1)
        ):
            assert importer._run_per_comic_phases_chunked()  # noqa: SLF001
        importer.fail_imports()
        importer.delete()
        importer.full_text_search()

        assert self._universes_column(paths["a2"]) == "11,Alpha"
        assert self._universes_column(paths["b2"]) == "22,Beta"

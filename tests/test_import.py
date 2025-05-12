"""Test extract metadata importer."""

from pathlib import Path

from django.test import TestCase

from codex.librarian.importer.importer import ComicImporter
from codex.librarian.importer.tasks import ImportDBDiffTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.mp_queue import LOG_QUEUE

PATH = str(Path(__file__).parent / "files/comicbox-2-example.cbz")
TASK = ImportDBDiffTask(1, files_modified=frozenset({PATH}))


class TestImporterImport(TestCase):
    def test_importer_import(self):
        importer = ComicImporter(TASK, LOG_QUEUE, LIBRARIAN_QUEUE)
        importer.apply()
        assert True


if __name__ == "__main__":
    TestImporterImport().test_importer_import()

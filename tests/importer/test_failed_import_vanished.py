"""
Failed imports for files that no longer exist are not recorded.

A file renamed out from under a running import fails to read, but the
failure belongs to a path that no longer exists — recording it leaves a
permanent phantom row in the admin's failed imports panel.
"""

from threading import Event, Lock
from typing import override

from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.const import FIS
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.models import FailedImport, Library
from tests.importer.test_basic import LIBRARY_PATH, PATH, BaseTestImporter

_VANISHED = str(LIBRARY_PATH / "gone.cbz")


class TestFailedImportVanished(BaseTestImporter):
    """Only failures for files still on disk become rows."""

    @override
    def setUp(self) -> None:
        super().setUp()
        task = ImportTask(library_id=self.task.library_id)
        self.fi_importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())

    def test_vanished_path_creates_no_row(self) -> None:
        self.fi_importer.metadata[FIS] = {_VANISHED: ValueError("does not exist")}

        self.fi_importer.fail_imports()

        assert FailedImport.objects.count() == 0

    def test_existing_path_creates_row(self) -> None:
        self.fi_importer.metadata[FIS] = {PATH: ValueError("bad tags")}

        self.fi_importer.fail_imports()

        fi = FailedImport.objects.get(path=PATH)
        assert "bad tags" in fi.name

    def test_repeated_failure_updates_row(self) -> None:
        library = Library.objects.get(pk=self.task.library_id)
        old = FailedImport(library=library, path=PATH)
        old.set_reason(ValueError("first reason"))
        old.presave()
        old.save()
        self.fi_importer.metadata[FIS] = {PATH: ValueError("second reason")}

        self.fi_importer.fail_imports()

        assert FailedImport.objects.count() == 1
        fi = FailedImport.objects.get(path=PATH)
        assert "second reason" in fi.name

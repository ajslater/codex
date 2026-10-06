"""
Failed imports for files that no longer exist are not recorded.

A file renamed out from under a running import fails to read, but the
failure belongs to a path that no longer exists — recording it leaves a
permanent phantom row in the admin's failed imports panel.

Existing rows for files that are still on disk survive later imports;
rows for files that are gone are cleaned up.
"""

from pathlib import Path
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

    def _create_failed_import(self, path: str) -> None:
        """Record an earlier import's failure; unstatted, so the path may be gone."""
        library = Library.objects.get(pk=self.task.library_id)
        FailedImport.objects.create(library=library, path=path, name="old reason")

    def test_untouched_row_for_existing_file_survives(self) -> None:
        """
        A still-failing file that this import didn't touch keeps its row.

        The existence check compared the whole casefolded path to each
        sibling's basename, so it never matched and every untouched row
        was deleted after any import.
        """
        self._create_failed_import(PATH)

        self.fi_importer.fail_imports()

        assert FailedImport.objects.filter(path=PATH).exists()

    def test_untouched_row_for_vanished_file_is_deleted(self) -> None:
        self._create_failed_import(_VANISHED)

        self.fi_importer.fail_imports()

        assert not FailedImport.objects.filter(path=_VANISHED).exists()

    def test_untouched_row_with_stale_case_is_deleted(self) -> None:
        """The match is case sensitive, unlike ``exists()`` on macOS."""
        stale_case = str(LIBRARY_PATH / Path(PATH).name.upper())
        self._create_failed_import(stale_case)

        self.fi_importer.fail_imports()

        assert not FailedImport.objects.filter(path=stale_case).exists()

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

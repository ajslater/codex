"""
Deletes are confirmed against the filesystem before they cascade.

Both scanners *infer* deletes, and every inference has failure modes that
name a path still sitting on disk — a split watch batch, an overmatched
directory expansion, a refused inode pair. Acting on one destroys the
comic's bookmarks and read progress permanently, so the delete phase
checks the disk first and leaves anything still there for the next scan.
"""

import shutil
from pathlib import Path
from threading import Event, Lock
from typing import override
from unittest.mock import MagicMock

from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.models import (
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from tests.importer.test_basic import (
    COMIC_PATH,
    LIBRARY_PATH,
    BaseTestImporter,
)

_GONE = str(LIBRARY_PATH / "gone.cbz")
_EXTANT = str(LIBRARY_PATH / "still-here.cbz")
_SUBDIR = LIBRARY_PATH / "subdir"


class _DeleteTestBase(BaseTestImporter):
    """A library with a folder row and comic-creation helpers."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.library = Library.objects.get(pk=self.task.library_id)
        self.folder = Folder.objects.create(
            library=self.library, path=str(LIBRARY_PATH), name=LIBRARY_PATH.name
        )
        pub = Publisher.objects.create(name="Delete Pub")
        imp = Imprint.objects.create(name="Delete Imprint", publisher=pub)
        ser = Series.objects.create(name="Delete Series", imprint=imp, publisher=pub)
        self.tags = {
            "publisher": pub,
            "imprint": imp,
            "series": ser,
            "volume": Volume.objects.create(
                name="1", series=ser, imprint=imp, publisher=pub
            ),
        }
        self.issue_number = 0

    def _create_comic(self, path: str, folder: Folder | None = None) -> Comic:
        """Create a comic with its file present, as presave stats disk."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(COMIC_PATH, path)
        self.issue_number += 1
        comic = Comic.objects.create(
            library=self.library,
            path=path,
            parent_folder=folder or self.folder,
            issue_number=self.issue_number,
            name=Path(path).stem,
            size=1,
            page_count=1,
            **self.tags,
        )
        comic.folders.add(folder or self.folder)
        return comic

    def _make_subdir_folder(self) -> Folder:
        """Track a subdirectory, present on disk as its row requires."""
        _SUBDIR.mkdir(parents=True, exist_ok=True)
        return Folder.objects.create(
            library=self.library, path=str(_SUBDIR), name=_SUBDIR.name
        )

    def _delete(self, **task_kwargs) -> ComicImporter:
        """Run the delete phase with a fresh importer, as a scan would."""
        task = ImportTask(library_id=self.library.pk, **task_kwargs)
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())
        importer.delete()
        return importer


class TestDeleteExistenceBackstop(_DeleteTestBase):
    """A path still on disk is never deleted from the database."""

    def test_comic_still_on_disk_is_not_deleted(self) -> None:
        """The whole point: a wrongly reported delete keeps its row."""
        comic = self._create_comic(_EXTANT)

        importer = self._delete(files_deleted=frozenset({_EXTANT}))

        assert Comic.objects.filter(pk=comic.pk).exists()
        assert importer.counts.comics_deleted == 0

    def test_comic_missing_from_disk_is_deleted(self) -> None:
        """A real delete still deletes."""
        comic = self._create_comic(_GONE)
        Path(_GONE).unlink()

        importer = self._delete(files_deleted=frozenset({_GONE}))

        assert not Comic.objects.filter(pk=comic.pk).exists()
        assert importer.counts.comics_deleted == 1

    def test_only_the_extant_path_is_spared(self) -> None:
        """A mixed batch deletes what is gone and keeps what isn't."""
        gone = self._create_comic(_GONE)
        extant = self._create_comic(_EXTANT)
        Path(_GONE).unlink()

        self._delete(files_deleted=frozenset({_GONE, _EXTANT}))

        assert not Comic.objects.filter(pk=gone.pk).exists()
        assert Comic.objects.filter(pk=extant.pk).exists()

    def test_folder_still_on_disk_is_not_deleted(self) -> None:
        """A folder delete that would cascade comics is checked too."""
        subdir_folder = self._make_subdir_folder()
        comic = self._create_comic(str(_SUBDIR / "c.cbz"), folder=subdir_folder)

        self._delete(dirs_deleted=frozenset({str(_SUBDIR)}))

        assert Folder.objects.filter(pk=subdir_folder.pk).exists()
        assert Comic.objects.filter(pk=comic.pk).exists()

    def test_deleted_folder_cascade_is_counted_and_restamped(self) -> None:
        """Comics dying by folder cascade are counted, and re-stamp their series."""
        subdir_folder = self._make_subdir_folder()
        comic = self._create_comic(str(_SUBDIR / "c.cbz"), folder=subdir_folder)
        series_pk = comic.series.pk
        stamped_before = Series.objects.get(pk=series_pk).updated_at
        shutil.rmtree(_SUBDIR)

        importer = self._delete(dirs_deleted=frozenset({str(_SUBDIR)}))

        assert not Comic.objects.filter(pk=comic.pk).exists()
        # Counted as one folder and one comic, not one folder-shaped comic.
        assert importer.counts.folders_deleted == 1
        assert importer.counts.comics_deleted == 1
        # The emptied series must be re-stamped or browsers keep listing it.
        assert Series.objects.get(pk=series_pk).updated_at > stamped_before


class TestMassDeleteWarning(_DeleteTestBase):
    """A delete big enough to look like a vanished mount is flagged."""

    def _importer(self) -> tuple[ComicImporter, MagicMock]:
        """Build an importer whose log is captured for assertions."""
        task = ImportTask(library_id=self.library.pk)
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())
        mock_log = MagicMock()
        importer.log = mock_log
        return importer, mock_log

    def test_small_delete_is_quiet(self) -> None:
        """Ordinary tidying up must not cry wolf."""
        self._create_comic(_EXTANT)
        importer, mock_log = self._importer()

        importer._warn_on_mass_delete(1)  # noqa: SLF001

        mock_log.warning.assert_not_called()

    def test_large_delete_warns(self) -> None:
        """Losing most of a library logs where to look."""
        self._create_comic(_EXTANT)
        importer, mock_log = self._importer()

        importer._warn_on_mass_delete(500)  # noqa: SLF001

        mock_log.warning.assert_called_once()
        assert "mounted" in mock_log.warning.call_args[0][0]

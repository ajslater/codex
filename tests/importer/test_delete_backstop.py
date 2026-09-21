"""
Deletes are confirmed against the filesystem before they cascade.

Both scanners *infer* deletes, and every inference has failure modes that
name a path still sitting on disk — a split watch batch, an overmatched
directory expansion, a refused inode pair, a directory that would not
answer. Acting on one destroys the comic's bookmarks and read progress
permanently, so the delete phase checks the disk first and leaves anything
still there for the next scan.

The check fails closed: only "no such file" means gone. A permission or
I/O error means the filesystem could not answer, which is not the same
thing, and a folder delete probes the comics its cascade would take as
well as its own path.

"No such file" is not proof either, once, so the delete phase takes a
second look: it probes, waits, and re-probes whatever came back missing,
keeping anything that answers the second time.
"""

import os
import shutil
import threading
from pathlib import Path
from threading import Event, Lock
from typing import Final, override
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.db.models.functions import Now
from loguru import logger

from codex.librarian.covers.tasks import CoverCreateTask, CoverRemoveTask
from codex.librarian.fs.import_task import build_import_task
from codex.librarian.fs.poller.poller import LibraryPollerThread
from codex.librarian.fs.poller.snapshot import DatabaseSnapshot, DiskSnapshot
from codex.librarian.fs.poller.snapshot_diff import SnapshotDiff
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.librarian.scribe.importer.delete.existence import SECOND_LOOK_DELAY_S
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.janitor.integrity.foreign_keys import fix_folder_relations
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.models import (
    Bookmark,
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
_EACCES: Final = PermissionError(13, "Permission denied")
_BOOKMARKED_COMICS: Final = 3
_BOOKMARK_PAGE: Final = 140


class _DeleteTestBase(BaseTestImporter):
    """A library with a folder row and comic-creation helpers."""

    @override
    def setUp(self) -> None:
        super().setUp()
        # Every delete-bearing batch waits between its two probes. Patch
        # the wait rather than shortening it, so the tests assert *that*
        # it waited without any of them paying for it.
        wait_patcher = patch.object(threading.Event, "wait")
        self.wait_mock = wait_patcher.start()
        self.addCleanup(wait_patcher.stop)
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


def _stat_failing_for(targets: frozenset[str], error: OSError):
    """Return a Path.stat that answers the way a sick filesystem did."""
    real_stat = Path.stat

    def fake_stat(self, *args, **kwargs):
        if str(self) in targets:
            raise error
        return real_stat(self, *args, **kwargs)

    return fake_stat


def _stat_reviving(targets: frozenset[str]):
    """Return a Path.stat that answers gone once, then tells the truth."""
    real_stat = Path.stat
    answered_gone: set[str] = set()

    def fake_stat(self, *args, **kwargs):
        path = str(self)
        if path in targets and path not in answered_gone:
            answered_gone.add(path)
            raise FileNotFoundError(2, "No such file or directory", path)
        return real_stat(self, *args, **kwargs)

    return fake_stat


def _scandir_failing_for(target: Path, error: OSError):
    """Return an os.scandir that refuses to list one directory."""
    real_scandir = os.scandir

    def fake_scandir(path):
        if Path(path) == target:
            raise error
        return real_scandir(path)

    return fake_scandir


class TestDeleteFailsClosedOnUnreadable(_DeleteTestBase):
    """A path that could not be read is not a path that is gone."""

    def _bookmark(self, comic: Comic) -> Bookmark:
        user = User.objects.create_user(username=f"reader{comic.pk}", password="x")  # noqa: S106
        return Bookmark.objects.create(user=user, comic=comic, finished=True)

    def test_unreadable_comic_keeps_its_row_and_bookmark(self) -> None:
        """The whole point: EACCES must never cascade a bookmark away."""
        comic = self._create_comic(_EXTANT)
        bookmark = self._bookmark(comic)

        with patch.object(
            Path, "stat", _stat_failing_for(frozenset({_EXTANT}), _EACCES)
        ):
            importer = self._delete(files_deleted=frozenset({_EXTANT}))

        assert Comic.objects.filter(pk=comic.pk).exists()
        assert Bookmark.objects.filter(pk=bookmark.pk).exists()
        assert importer.counts.comics_deleted == 0

    def test_unreadable_folder_keeps_its_subtree(self) -> None:
        """One unreadable directory used to take every comic under it."""
        subdir_folder = self._make_subdir_folder()
        comic = self._create_comic(str(_SUBDIR / "c.cbz"), folder=subdir_folder)
        bookmark = self._bookmark(comic)
        targets = frozenset({str(_SUBDIR), str(_SUBDIR / "c.cbz")})

        with patch.object(Path, "stat", _stat_failing_for(targets, _EACCES)):
            self._delete(dirs_deleted=frozenset({str(_SUBDIR)}))

        assert Folder.objects.filter(pk=subdir_folder.pk).exists()
        assert Comic.objects.filter(pk=comic.pk).exists()
        assert Bookmark.objects.filter(pk=bookmark.pk).exists()

    def test_unreadable_paths_are_reported(self) -> None:
        """An EACCES storm must be visible, not silently destructive."""
        self._create_comic(_EXTANT)
        task = ImportTask(
            library_id=self.library.pk, files_deleted=frozenset({_EXTANT})
        )
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())
        mock_log = MagicMock()
        importer.log = mock_log

        with patch.object(
            Path, "stat", _stat_failing_for(frozenset({_EXTANT}), _EACCES)
        ):
            importer.delete()

        warnings = [call.args[0] for call in mock_log.warning.call_args_list]
        assert any("could not be checked" in warning for warning in warnings), warnings

    def test_missing_comic_under_an_answering_folder_is_still_deleted(self) -> None:
        """Failing closed must not stop real deletes from landing."""
        comic = self._create_comic(_GONE)
        Path(_GONE).unlink()

        importer = self._delete(files_deleted=frozenset({_GONE}))

        assert not Comic.objects.filter(pk=comic.pk).exists()
        assert importer.counts.comics_deleted == 1


class TestFolderCascadeIsProbed(_DeleteTestBase):
    """The comics a folder delete cascades are checked, not assumed."""

    def test_extant_comic_saves_its_folder(self) -> None:
        """A folder reported gone whose comic is still there keeps both."""
        subdir_folder = self._make_subdir_folder()
        comic = self._create_comic(str(_SUBDIR / "c.cbz"), folder=subdir_folder)
        # The folder path answers "gone" while its comic stats fine — an
        # incoherent answer only a sick filesystem gives, and the last
        # line of defense before the cascade.
        gone = frozenset({str(_SUBDIR)})

        with patch.object(
            Path, "stat", _stat_failing_for(gone, FileNotFoundError(2, "No such file"))
        ):
            importer = self._delete(dirs_deleted=gone)

        assert Folder.objects.filter(pk=subdir_folder.pk).exists()
        assert Comic.objects.filter(pk=comic.pk).exists()
        assert importer.counts.folders_deleted == 0

    def test_ancestor_folder_is_trimmed_too(self) -> None:
        """Folder.parent_folder cascades, so an ancestor would take the child."""
        subdir_folder = self._make_subdir_folder()
        nested_path = _SUBDIR / "nested"
        nested_path.mkdir(parents=True, exist_ok=True)
        nested_folder = Folder.objects.create(
            library=self.library,
            path=str(nested_path),
            name="nested",
            parent_folder=subdir_folder,
        )
        comic = self._create_comic(str(nested_path / "deep.cbz"), folder=nested_folder)
        gone = frozenset({str(_SUBDIR), str(nested_path)})

        with patch.object(
            Path, "stat", _stat_failing_for(gone, FileNotFoundError(2, "No such file"))
        ):
            self._delete(dirs_deleted=gone)

        # Neither the parent nor the child may go: both are above a comic
        # that is still on disk.
        assert Folder.objects.filter(pk=subdir_folder.pk).exists()
        assert Folder.objects.filter(pk=nested_folder.pk).exists()
        assert Comic.objects.filter(pk=comic.pk).exists()

    def test_real_folder_delete_still_cascades(self) -> None:
        """Nothing here may stop a genuine directory removal."""
        subdir_folder = self._make_subdir_folder()
        comic = self._create_comic(str(_SUBDIR / "c.cbz"), folder=subdir_folder)
        shutil.rmtree(_SUBDIR)

        importer = self._delete(dirs_deleted=frozenset({str(_SUBDIR)}))

        assert not Folder.objects.filter(pk=subdir_folder.pk).exists()
        assert not Comic.objects.filter(pk=comic.pk).exists()
        assert importer.counts.comics_deleted == 1

    def test_cascade_is_announced(self) -> None:
        """The one destructive path that never named its victims now does."""
        subdir_folder = self._make_subdir_folder()
        self._create_comic(str(_SUBDIR / "c.cbz"), folder=subdir_folder)
        shutil.rmtree(_SUBDIR)
        task = ImportTask(
            library_id=self.library.pk, dirs_deleted=frozenset({str(_SUBDIR)})
        )
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())
        mock_log = MagicMock()
        importer.log = mock_log

        importer.delete()

        infos = [call.args[0] for call in mock_log.info.call_args_list]
        assert any("comics under" in info for info in infos), infos


class TestUnreadableSubtreeEndToEnd(_DeleteTestBase):
    """Poll an unreadable publisher directory; lose nothing."""

    def _poll_and_delete(self) -> None:
        """Run the poller's diff and the importer's delete phase, as a poll does."""
        db_snapshot = DatabaseSnapshot(self.library.path, logger)
        disk_snapshot = DiskSnapshot(self.library.path, logger)
        diff = SnapshotDiff(db_snapshot, disk_snapshot)
        # The poller passes ``soft_delete=True``; mirror it so this test
        # exercises the path production takes.
        task = build_import_task(self.library.pk, diff.to_events(), soft_delete=True)
        if task is None:
            return
        # Nothing under the unreadable directory may even be proposed.
        assert not [path for path in task.files_deleted if str(_SUBDIR) in path]
        assert not [path for path in task.dirs_deleted if str(_SUBDIR) in path]
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())
        importer.delete()

    def test_bookmarks_survive_an_unreadable_publisher_directory(self) -> None:
        """The reporter's incident, start to finish."""
        subdir_folder = self._make_subdir_folder()
        comics = [
            self._create_comic(str(_SUBDIR / f"c{index}.cbz"), folder=subdir_folder)
            for index in range(_BOOKMARKED_COMICS)
        ]
        user = User.objects.create_user(username="reader", password="x")  # noqa: S106
        for comic in comics:
            Bookmark.objects.create(user=user, comic=comic, finished=True)
        pks = sorted(comic.pk for comic in comics)

        with patch.object(
            os, "scandir", side_effect=_scandir_failing_for(_SUBDIR, _EACCES)
        ):
            self._poll_and_delete()

        assert (
            sorted(Comic.objects.filter(pk__in=pks).values_list("pk", flat=True)) == pks
        )
        assert (
            Bookmark.objects.filter(comic__pk__in=pks, finished=True).count()
            == _BOOKMARKED_COMICS
        )
        assert Folder.objects.filter(pk=subdir_folder.pk).exists()

        # The share recovers: the next poll must still change nothing,
        # rather than re-importing the comics as new unread rows.
        self._poll_and_delete()

        assert (
            sorted(Comic.objects.filter(pk__in=pks).values_list("pk", flat=True)) == pks
        )
        assert (
            Bookmark.objects.filter(comic__pk__in=pks, finished=True).count()
            == _BOOKMARKED_COMICS
        )


class TestSecondLookBeforeDeleting(_DeleteTestBase):
    """A path that answers on a second probe was never gone."""

    def _bookmark(self, comic: Comic) -> Bookmark:
        user = User.objects.create_user(username=f"reader{comic.pk}", password="x")  # noqa: S106
        return Bookmark.objects.create(user=user, comic=comic, finished=True)

    def test_comic_that_comes_back_keeps_row_and_bookmark(self) -> None:
        """A share that lies for a moment must not cost a comic its place."""
        gone = self._create_comic(_GONE)
        Path(_GONE).unlink()
        flapping = self._create_comic(_EXTANT)
        bookmark = self._bookmark(flapping)

        with patch.object(Path, "stat", _stat_reviving(frozenset({_EXTANT}))):
            importer = self._delete(files_deleted=frozenset({_GONE, _EXTANT}))

        assert Comic.objects.filter(pk=flapping.pk).exists()
        assert Bookmark.objects.filter(pk=bookmark.pk).exists()
        # The one that really is gone still goes.
        assert not Comic.objects.filter(pk=gone.pk).exists()
        assert importer.counts.comics_deleted == 1
        self.wait_mock.assert_called_once_with(SECOND_LOOK_DELAY_S)

    def test_folder_that_comes_back_keeps_subtree(self) -> None:
        """The cascade is what makes a flapping directory expensive."""
        subdir_folder = self._make_subdir_folder()
        comic = self._create_comic(str(_SUBDIR / "c.cbz"), folder=subdir_folder)
        bookmark = self._bookmark(comic)

        with patch.object(Path, "stat", _stat_reviving(frozenset({str(_SUBDIR)}))):
            importer = self._delete(dirs_deleted=frozenset({str(_SUBDIR)}))

        assert Folder.objects.filter(pk=subdir_folder.pk).exists()
        assert Comic.objects.filter(pk=comic.pk).exists()
        assert Bookmark.objects.filter(pk=bookmark.pk).exists()
        assert importer.counts.folders_deleted == 0

    def test_nothing_gone_means_no_wait(self) -> None:
        """A healthy scan must not stall the scribe for five seconds."""
        self._create_comic(_EXTANT)

        self._delete(files_deleted=frozenset({_EXTANT}))

        self.wait_mock.assert_not_called()

    def test_empty_batch_means_no_wait(self) -> None:
        """Neither must a batch with no deletes at all."""
        self._delete()

        self.wait_mock.assert_not_called()

    def test_mixed_batch_waits_once(self) -> None:
        """One wait per batch, however many paths it carries."""
        subdir_folder = self._make_subdir_folder()
        comic = self._create_comic(str(_SUBDIR / "c.cbz"), folder=subdir_folder)
        shutil.rmtree(_SUBDIR)
        gone = self._create_comic(_GONE)
        Path(_GONE).unlink()

        self._delete(
            dirs_deleted=frozenset({str(_SUBDIR)}),
            files_deleted=frozenset({_GONE}),
        )

        assert not Folder.objects.filter(pk=subdir_folder.pk).exists()
        assert not Comic.objects.filter(pk=comic.pk).exists()
        assert not Comic.objects.filter(pk=gone.pk).exists()
        self.wait_mock.assert_called_once_with(SECOND_LOOK_DELAY_S)

    def test_revival_is_reported(self) -> None:
        """A flapping filesystem is worth a line in the log."""
        self._create_comic(_EXTANT)
        task = ImportTask(
            library_id=self.library.pk, files_deleted=frozenset({_EXTANT})
        )
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())
        mock_log = MagicMock()
        importer.log = mock_log

        with patch.object(Path, "stat", _stat_reviving(frozenset({_EXTANT}))):
            importer.delete()

        warnings = [call.args[0] for call in mock_log.warning.call_args_list]
        assert any("answered" in warning for warning in warnings), warnings


class TestSoftDeleteStamping(_DeleteTestBase):
    """
    A poller-inferred delete keeps the row and records when it vanished.

    The reporter's comics were missing for 41-50 minutes across two
    incidents, far longer than the five-second second look covers, and a
    whole publisher's read progress was destroyed each time. Retention
    is the answer to a *sustained* outage, which the existing guards say
    outright they do not cover.
    """

    def _soft_delete(self, **task_kwargs) -> ComicImporter:
        """Run the delete phase the way the poller asks for it."""
        return self._delete(soft_delete=True, **task_kwargs)

    def test_a_vanished_comic_keeps_its_row_and_its_bookmark(self) -> None:
        """The headline behaviour, and the thing being protected."""
        comic = self._create_comic(_GONE)
        user = User.objects.create_user(username="reader", password="x")  # noqa: S106
        Bookmark.objects.create(user=user, comic=comic, page=140, finished=False)
        Path(_GONE).unlink()

        importer = self._soft_delete(files_deleted=frozenset({_GONE}))

        comic.refresh_from_db()
        assert comic.missing_since is not None
        assert Bookmark.objects.get(comic=comic).page == _BOOKMARK_PAGE
        assert importer.counts.comics_missing == 1
        assert importer.counts.comics_deleted == 0

    def test_a_watcher_delete_still_deletes(self) -> None:
        """
        Retention is poller-only, and the default is unchanged.

        A watcher ``deleted`` means the OS observed the name vanish at
        that instant, with no "the walk could not look" failure mode.
        The poller also re-observes on every pass, which is what makes
        retention possible; the watcher cannot.
        """
        comic = self._create_comic(_GONE)
        Path(_GONE).unlink()

        importer = self._delete(files_deleted=frozenset({_GONE}))

        assert not Comic.objects.filter(pk=comic.pk).exists()
        assert importer.counts.comics_deleted == 1
        assert importer.counts.comics_missing == 0

    def test_an_unreadable_path_is_never_stamped(self) -> None:
        """
        The trap the design names.

        A path that could not be read is not a path that is gone.
        ``confirm_deleted`` returns only the ENOENT bucket, so a
        permission error leaves the row completely untouched -- not
        stamped, not deleted.
        """
        comic = self._create_comic(_EXTANT)
        with patch.object(
            Path, "stat", _stat_failing_for(frozenset({_EXTANT}), _EACCES)
        ):
            importer = self._soft_delete(files_deleted=frozenset({_EXTANT}))

        comic.refresh_from_db()
        assert comic.missing_since is None
        assert importer.counts.comics_missing == 0

    def test_a_second_pass_does_not_reset_the_clock(self) -> None:
        """
        Without this guard the window never expires.

        A stamped row stays in the poller's reference snapshot, so the
        same vanished path is re-emitted on every poll. If each pass
        rewrote ``missing_since`` the reaper would never see a row old
        enough to reap, and the retention window would be infinite.
        """
        comic = self._create_comic(_GONE)
        Path(_GONE).unlink()
        self._soft_delete(files_deleted=frozenset({_GONE}))
        comic.refresh_from_db()
        first = comic.missing_since

        importer = self._soft_delete(files_deleted=frozenset({_GONE}))

        comic.refresh_from_db()
        assert comic.missing_since == first
        assert importer.counts.comics_missing == 0

    def test_a_vanished_folder_keeps_its_row(self) -> None:
        """A stamped folder takes nothing with it until the reaper runs."""
        subdir_folder = self._make_subdir_folder()
        shutil.rmtree(_SUBDIR)

        importer = self._soft_delete(dirs_deleted=frozenset({str(_SUBDIR)}))

        subdir_folder.refresh_from_db()
        assert subdir_folder.missing_since is not None
        assert importer.counts.folders_missing == 1
        assert importer.counts.folders_deleted == 0

    def test_the_stamp_is_not_re_reported_by_the_next_poll(self) -> None:
        """
        A pending row is reported once, not on every poll.

        Re-reporting would pay the second look's wait each pass, re-fire
        the mass-delete warning, keep ``diff.is_empty()`` permanently
        false, and make the importer's log claim a library is losing
        comics it still has.
        """
        self._create_comic(_GONE)
        Path(_GONE).unlink()
        self._soft_delete(files_deleted=frozenset({_GONE}))

        db_snapshot = DatabaseSnapshot(self.library.path, logger)
        disk_snapshot = DiskSnapshot(self.library.path, logger)
        diff = SnapshotDiff(db_snapshot, disk_snapshot)

        assert _GONE in db_snapshot.missing
        # Still in ``paths``: a file that comes back must keep its row
        # rather than read as ``added`` and mint a new one.
        assert _GONE in db_snapshot.paths
        assert _GONE not in diff.files_deleted


class TestJanitorSpares(_DeleteTestBase):
    """
    The nightly sweeps that would eat a stamped row before its window.

    Each one silently voids the retention guarantee, and none of them
    has an existence probe of its own.
    """

    def _stamp_folder(self, folder: Folder) -> None:
        Folder.objects.filter(pk=folder.pk).update(missing_since=Now())

    def test_prune_stale_folders_spares_a_stamped_folder(self) -> None:
        """
        Nightly, and it runs *before* the reaper.

        A stamped folder holds no comics precisely because they vanished
        with it, so it is in neither ``protected`` nor ``needed`` and
        would be deleted hours early -- cascading its comics and their
        bookmarks away, with no probe.
        """
        subdir_folder = self._make_subdir_folder()
        self._stamp_folder(subdir_folder)

        fix_folder_relations(logger)

        assert Folder.objects.filter(pk=subdir_folder.pk).exists()

    def test_cleanup_fks_spares_a_stamped_folder(self) -> None:
        """Same empty stamped folder, second chance to die the same night."""
        subdir_folder = self._make_subdir_folder()
        self._stamp_folder(subdir_folder)

        janitor = Janitor(logger, LIBRARIAN_QUEUE, Lock(), Event())
        janitor.cleanup_fks()

        assert Folder.objects.filter(pk=subdir_folder.pk).exists()

    def test_a_stamped_comic_does_not_resurrect_its_folders(self) -> None:
        """
        ``fix_folder_relations`` re-derives folder state from comic paths.

        Walking a stamped comic would recreate its reaped ancestors with
        a fresh pk and a NULL stamp -- un-hiding the subtree -- and
        ``Folder.objects.create`` stats the path in ``presave``, so a
        vanished dir raises an uncaught FileNotFoundError that kills the
        whole nightly integrity task mid-run.
        """
        # A stamped comic under a subdirectory that has no Folder row --
        # the state left behind once the reaper has taken the folder.
        # Its parent is the library root, so nothing cascades here.
        comic = self._create_comic(str(_SUBDIR / "c.cbz"))
        Comic.objects.filter(pk=comic.pk).update(missing_since=Now())
        shutil.rmtree(_SUBDIR)

        fix_folder_relations(logger)

        assert not Folder.objects.filter(path=str(_SUBDIR)).exists()
        assert Comic.objects.filter(pk=comic.pk).exists()

    def test_a_live_comic_still_gets_its_folders_created(self) -> None:
        """The guard above must not stop the repair it belongs to."""
        comic = self._create_comic(str(_SUBDIR / "live.cbz"))

        fix_folder_relations(logger)

        assert Folder.objects.filter(path=str(_SUBDIR)).exists()
        assert Comic.objects.filter(pk=comic.pk).exists()


class TestRevival(_DeleteTestBase):
    """
    A file that comes back reuses its row, and its bookmarks with it.

    Without this the feature is net-negative: the row stays hidden until
    the reaper hard-deletes it, and the *next* poll sees the path as
    ``added`` and imports it as a fresh comic with no bookmarks -- the
    original bug, delayed by a day and now silent, because the
    intervening day of invisibility looks like the feature working.
    """

    def _poller(self) -> LibraryPollerThread:
        """Build a poller without starting the threading machinery."""
        thread = LibraryPollerThread.__new__(LibraryPollerThread)
        # The loguru re-export the poller annotates against is a
        # different type than the module-level ``logger`` here.
        thread.log = MagicMock(wraps=logger)
        thread.librarian_queue = LIBRARIAN_QUEUE
        thread.db_write_lock = Lock()
        return thread

    def _unstamp(self) -> None:
        """Run the poller's revival pass, as a poll does."""
        db_snapshot = DatabaseSnapshot(self.library.path, logger)
        disk_snapshot = DiskSnapshot(self.library.path, logger)
        diff = SnapshotDiff(db_snapshot, disk_snapshot)
        self._poller()._unstamp_revived(self.library, diff)  # noqa: SLF001

    def _vanish(self, comic: Comic) -> None:
        """Take the file away and let a poll-style delete stamp the row."""
        Path(comic.path).unlink()
        self._delete(soft_delete=True, files_deleted=frozenset({comic.path}))
        comic.refresh_from_db()
        assert comic.missing_since is not None

    def test_revival_with_an_unchanged_stat(self) -> None:
        """
        The case the whole feature turns on, and the one that fails today.

        A remount, a share that reconnected, an unmount/mount cycle: the
        file is back with the same mtime and size, so the diff produces
        no entry at all -- neither added nor deleted nor modified -- and
        the poll would otherwise report "Nothing changed" forever.
        """
        comic = self._create_comic(_GONE)
        user = User.objects.create_user(username="reader", password="x")  # noqa: S106
        Bookmark.objects.create(user=user, comic=comic, page=_BOOKMARK_PAGE)
        pk = comic.pk
        stat = Path(_GONE).stat()

        self._vanish(comic)
        # Restore byte-identically, mtime included.
        shutil.copy(COMIC_PATH, _GONE)
        os.utime(_GONE, (stat.st_atime, stat.st_mtime))

        self._unstamp()

        comic.refresh_from_db()
        assert comic.pk == pk
        assert comic.missing_since is None
        assert Bookmark.objects.get(comic=comic).page == _BOOKMARK_PAGE

    def test_revival_with_a_changed_stat(self) -> None:
        """A file rewritten while it was away still reuses its row."""
        comic = self._create_comic(_GONE)
        pk = comic.pk
        self._vanish(comic)
        shutil.copy(COMIC_PATH, _GONE)
        os.utime(_GONE, (0, 0))

        self._unstamp()

        comic.refresh_from_db()
        assert comic.pk == pk
        assert comic.missing_since is None

    def test_a_still_missing_comic_keeps_its_stamp(self) -> None:
        """The pass must only clear what actually came back."""
        comic = self._create_comic(_GONE)
        self._vanish(comic)
        stamped_at = comic.missing_since

        self._unstamp()

        comic.refresh_from_db()
        assert comic.missing_since == stamped_at

    def test_revival_announces_itself(self) -> None:
        """
        The unstamp is a bare update outside any import.

        Nothing else clears the caches or tells a client, so without
        this the comic comes back in the database and stays invisible in
        the browser until some unrelated import happens to run.
        """
        comic = self._create_comic(_GONE)
        self._vanish(comic)
        shutil.copy(COMIC_PATH, _GONE)

        with patch.object(LIBRARIAN_QUEUE, "put") as put_mock:
            self._unstamp()

        queued = [call.args[0] for call in put_mock.call_args_list]
        assert LIBRARY_CHANGED_TASK in queued, queued
        assert any(isinstance(task, CoverRemoveTask) for task in queued), queued
        assert any(isinstance(task, CoverCreateTask) for task in queued), queued

    def test_a_new_file_at_a_stamped_path_revives_the_row(self) -> None:
        """
        ``unique_together`` still holds for a stamped row.

        A genuinely new file cannot be inserted at that path during the
        window, so the stamp has to clear and the row be reused. That is
        also the better answer: the pk and its bookmarks belong to the
        path, and the import that follows overwrites the metadata.
        """
        comic = self._create_comic(_GONE)
        pk = comic.pk
        self._vanish(comic)
        # Different content at the same path.
        Path(_GONE).write_bytes(b"not the same file at all")

        self._unstamp()

        comic.refresh_from_db()
        assert comic.pk == pk
        assert comic.missing_since is None

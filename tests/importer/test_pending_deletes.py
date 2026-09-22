"""
A poller-inferred delete is held, not applied, until its window expires.

The backstop next door rejects a delete the filesystem contradicts. This
is the other half: a delete the filesystem *confirms* is still only one
observation, and the reporter's comics were gone for 41-50 minutes at a
stretch -- far longer than the five-second second look covers -- with a
whole publisher's read progress destroyed each time.

So a poll-inferred delete stamps ``missing_since`` and keeps the row.
The nightly sweeps have to spare a stamped row, a file that comes back
has to reclaim its own row and its bookmarks with it, and only the
reaper, a day later, finally applies the delete.
"""

import os
import shutil
from datetime import timedelta
from pathlib import Path
from threading import Event, Lock
from typing import Final
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.db.models.functions import Now
from django.utils import timezone
from loguru import logger

from codex.librarian.covers.tasks import CoverCreateTask, CoverRemoveTask
from codex.librarian.fs.poller.poller import LibraryPollerThread
from codex.librarian.fs.poller.snapshot import DatabaseSnapshot, DiskSnapshot
from codex.librarian.fs.poller.snapshot_diff import SnapshotDiff
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.janitor.integrity.foreign_keys import fix_folder_relations
from codex.librarian.scribe.janitor.janitor import (
    _JANITOR_METHOD_MAP,
    _NIGHTLY_TASKS,
    Janitor,
)
from codex.librarian.scribe.janitor.tasks import (
    JanitorCleanFKsTask,
    JanitorReapPendingDeletesTask,
)
from codex.librarian.scribe.priority import _SCRIBE_TASK_PRIORITY, get_task_priority
from codex.librarian.scribe.search.tasks import SearchIndexSyncTask
from codex.models import Bookmark, Comic, Folder
from tests.importer.test_basic import COMIC_PATH
from tests.importer.test_delete_backstop import (
    _EACCES,
    _EXTANT,
    _GONE,
    _SUBDIR,
    _DeleteTestBase,
    _stat_failing_for,
)

_BOOKMARK_PAGE: Final = 140


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


class TestReaper(_DeleteTestBase):
    """
    The nightly reaper, and the cascade it must refuse.

    Until the window expires nothing here deletes anything; after it,
    the delete is the ordinary one -- so the only interesting behaviour
    is the boundary and the guard.
    """

    def _janitor(self) -> Janitor:
        return Janitor(logger, LIBRARIAN_QUEUE, Lock(), Event())

    def _age(self, model, pk, *, hours: int) -> None:
        """Backdate a stamp so the window has or has not expired."""
        when = timezone.now() - timedelta(hours=hours)
        model.objects.filter(pk=pk).update(missing_since=when)

    def test_a_fresh_stamp_is_not_reaped(self) -> None:
        """The whole point of the delay."""
        comic = self._create_comic(_GONE)
        self._age(Comic, comic.pk, hours=1)

        self._janitor().reap_pending_deletes()

        assert Comic.objects.filter(pk=comic.pk).exists()

    def test_an_expired_stamp_is_reaped(self) -> None:
        """After the window the delete is the ordinary one."""
        comic = self._create_comic(_GONE)
        self._age(Comic, comic.pk, hours=25)

        self._janitor().reap_pending_deletes()

        assert not Comic.objects.filter(pk=comic.pk).exists()

    def test_a_live_comic_is_never_reaped(self) -> None:
        """An unstamped row is not this job's business at all."""
        comic = self._create_comic(_EXTANT)

        self._janitor().reap_pending_deletes()

        assert Comic.objects.filter(pk=comic.pk).exists()

    def test_a_folder_with_a_live_comic_is_not_reaped(self) -> None:
        """
        The cascade guard.

        A folder delete cascades to its comics through
        ``Comic.parent_folder`` and to sub-folders through
        ``Folder.parent_folder``, so reaping a stamped ancestor would
        take live descendants -- and their bookmarks -- with it.
        """
        subdir_folder = self._make_subdir_folder()
        live = self._create_comic(str(_SUBDIR / "live.cbz"), folder=subdir_folder)
        self._age(Folder, subdir_folder.pk, hours=25)

        self._janitor().reap_pending_deletes()

        assert Folder.objects.filter(pk=subdir_folder.pk).exists()
        assert Comic.objects.filter(pk=live.pk).exists()

    def test_a_folder_whose_comics_all_expired_is_reaped(self) -> None:
        """Once nothing live remains below it, the subtree really is gone."""
        subdir_folder = self._make_subdir_folder()
        comic = self._create_comic(str(_SUBDIR / "gone.cbz"), folder=subdir_folder)
        self._age(Comic, comic.pk, hours=25)
        self._age(Folder, subdir_folder.pk, hours=25)

        self._janitor().reap_pending_deletes()

        assert not Comic.objects.filter(pk=comic.pk).exists()
        assert not Folder.objects.filter(pk=subdir_folder.pk).exists()

    def test_the_reap_announces_itself(self) -> None:
        """
        The janitor has no importer finish() to clear caches for it.

        ``cleanup_fks`` notifying nothing is a gap, not a precedent.
        """
        comic = self._create_comic(_GONE)
        self._age(Comic, comic.pk, hours=25)

        with patch.object(LIBRARIAN_QUEUE, "put") as put_mock:
            self._janitor().reap_pending_deletes()

        queued = [call.args[0] for call in put_mock.call_args_list]
        assert LIBRARY_CHANGED_TASK in queued, queued
        # The stamp deliberately kept the covers so a revived row would
        # find its own; now the row is really gone they must follow it.
        assert any(isinstance(task, CoverRemoveTask) for task in queued), queued

    def test_the_job_is_fully_registered(self) -> None:
        """
        A janitor job needs twelve registrations, not the three named in CLAUDE.md.

        Omitting the priority tuple is the silent-failure mode:
        ``get_task_priority`` raises ``ValueError: tuple.index(x): x not
        in tuple`` and the job simply never runs.
        """
        assert JanitorReapPendingDeletesTask in _SCRIBE_TASK_PRIORITY
        assert get_task_priority(JanitorReapPendingDeletesTask()) is not None
        assert any(
            isinstance(task, JanitorReapPendingDeletesTask) for task in _NIGHTLY_TASKS
        )
        assert _JANITOR_METHOD_MAP[JanitorReapPendingDeletesTask] == (
            "reap_pending_deletes"
        )
        assert hasattr(Janitor, "reap_pending_deletes")

    def test_the_reaper_runs_before_the_cleanups_that_depend_on_it(self) -> None:
        """
        Order matters, and it comes from the priority tuple's index.

        While a stamped comic still exists its Publisher/Imprint/Series/
        Volume are not orphaned, so an FK cleanup ahead of the reaper
        leaves emptied groups visible until the *next* night. The search
        sync likewise drops FTS rows whose comic is gone.
        """
        order = _SCRIBE_TASK_PRIORITY.index
        assert order(JanitorReapPendingDeletesTask) < order(JanitorCleanFKsTask)
        assert order(JanitorReapPendingDeletesTask) < order(SearchIndexSyncTask)
        assert order(JanitorReapPendingDeletesTask) > order(ImportTask)

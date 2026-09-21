"""
The nightly custom-cover cleanup fails closed on an unreadable path.

Deleting a ``CustomCover`` row is permanent in a way the comic delete
is not: ``BrowserCollectionModel.custom_cover`` is
``on_delete=SET_DEFAULT``, so the delete silently nulls the cover of
every collection pointing at it and nothing restores it. The admin has
to find and re-upload the image.

The probe had the same disease the comic delete path was cured of:
a parent directory that answered ``FileNotFoundError`` condemned its
whole group, and any other ``OSError`` fell back to ``Path.exists()``,
which swallows ``EACCES`` and returns ``False``. Both turn "I could not
look" into "it is not there".
"""

import os
import shutil
from pathlib import Path
from threading import Event, Lock
from typing import Final, override
from unittest.mock import patch

from django.test import TestCase
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.models import CustomCover

TMP_DIR = Path("/tmp/codex.tests.cleanup_custom_covers")  # noqa: S108
_EACCES: Final = PermissionError(13, "Permission denied")


#: Captured before any patch, for the same reason as ``_REAL_SCANDIR``.
_REAL_STAT = os.stat


def _stat_failing_for(targets: frozenset[str], error: OSError):
    """
    Return an ``os.stat`` that answers the way a sick filesystem did.

    Patched at the ``os`` level rather than on ``Path.stat`` because
    ``Path.exists()`` -- the call the old code relied on -- goes
    straight to ``os.stat`` and never sees a patched ``Path.stat``.
    Both the old path and the new ``probe_paths`` bottom out here.
    """

    def fake_stat(path, *args, **kwargs):
        if str(path) in targets:
            raise error
        return _REAL_STAT(path, *args, **kwargs)

    return fake_stat


#: Captured before any patch: ``cleanup`` imports the shared ``os``
#: module, so patching ``cleanup.os.scandir`` patches this name too and
#: a fake that called ``os.scandir`` would recurse into itself.
_REAL_SCANDIR = os.scandir


def _scandir_failing_for(target: Path, error: OSError):
    """Return an os.scandir that refuses to list one directory."""

    def fake_scandir(path):
        if Path(path) == target:
            raise error
        return _REAL_SCANDIR(path)

    return fake_scandir


class _ScandirList(list):
    """A list that satisfies ``with os.scandir(...) as it``."""

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> bool:
        return False


def _scandir_hiding(target: Path, basename: str):
    """Return an os.scandir that lists a directory without one entry."""

    def fake_scandir(path):
        with _REAL_SCANDIR(path) as it:
            entries = list(it)
        if Path(path) == target:
            entries = [entry for entry in entries if entry.name != basename]
        return _ScandirList(entries)

    return fake_scandir


class CleanupCustomCoversTestCase(TestCase):
    """A cover is only deleted when its file is really gone."""

    @override
    def setUp(self) -> None:
        """Two covers in one directory, both present on disk."""
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.covers: list[CustomCover] = []  # pyright: ignore[reportUninitializedInstanceVariable]
        for name in ("a.png", "b.png"):
            path = TMP_DIR / name
            path.write_bytes(b"not really a png")
            self.covers.append(CustomCover.objects.create(path=str(path)))
        # Patch the second look's wait so the tests assert *that* it
        # waited without any of them paying for it.
        wait_patcher = patch.object(Event, "wait")
        self.wait_mock = wait_patcher.start()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.addCleanup(wait_patcher.stop)

    @override
    def tearDown(self) -> None:
        """Remove the temp cover tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    @staticmethod
    def _cleanup() -> None:
        Janitor(logger, LIBRARIAN_QUEUE, Lock(), Event()).cleanup_custom_covers()

    def _surviving_pks(self) -> set[int]:
        return set(CustomCover.objects.values_list("pk", flat=True))

    def test_a_present_cover_is_kept(self) -> None:
        """Sanity: the healthy case still does nothing."""
        self._cleanup()
        assert self._surviving_pks() == {c.pk for c in self.covers}

    def test_a_really_deleted_cover_is_removed(self) -> None:
        """The job still does its job."""
        gone = self.covers[0]
        Path(gone.path).unlink()

        self._cleanup()

        assert self._surviving_pks() == {self.covers[1].pk}

    def test_an_unreadable_directory_keeps_its_covers(self) -> None:
        """
        A directory that would not list proves nothing about its covers.

        The old code fell back to ``Path.exists()`` here, which swallows
        EACCES and returns False -- so a permission blip on one folder
        permanently nulled every collection cover under it.
        """
        with (
            patch(
                "codex.librarian.scribe.janitor.cleanup.os.scandir",
                _scandir_failing_for(TMP_DIR, _EACCES),
            ),
            patch(
                "os.stat",
                _stat_failing_for(frozenset(str(c.path) for c in self.covers), _EACCES),
            ),
        ):
            self._cleanup()

        assert self._surviving_pks() == {c.pk for c in self.covers}

    def test_a_vanished_directory_does_not_condemn_its_group(self) -> None:
        """
        ENOENT on the parent looked exactly like a share mid-reconnect.

        The old code returned an empty name set for it, which marked
        every cover in the group orphaned in one step with no probe of
        its own. Now the parent proves nothing and each cover is probed
        -- and these two answer.
        """
        with patch(
            "codex.librarian.scribe.janitor.cleanup.os.scandir",
            _scandir_failing_for(
                TMP_DIR, FileNotFoundError(2, "No such file or directory")
            ),
        ):
            self._cleanup()

        assert self._surviving_pks() == {c.pk for c in self.covers}

    def test_a_cover_that_answers_on_the_second_look_is_kept(self) -> None:
        """
        One ENOENT is not proof, once.

        A share that lies for a moment during a reconnect answers
        exactly like a deleted file. The second look is what tells them
        apart.
        """
        flapping = str(self.covers[0].path)
        answered_gone: set[str] = set()

        def flapping_stat(path, *args, **kwargs):
            name = str(path)
            if name == flapping and name not in answered_gone:
                answered_gone.add(name)
                raise FileNotFoundError(2, "No such file or directory", name)
            return _REAL_STAT(path, *args, **kwargs)

        with (
            patch(
                "codex.librarian.scribe.janitor.cleanup.os.scandir",
                # The scandir pass reports it missing; the first probe
                # agrees, the re-probe finds it.
                _scandir_hiding(TMP_DIR, Path(flapping).name),
            ),
            patch("os.stat", flapping_stat),
        ):
            self._cleanup()

        assert self._surviving_pks() == {c.pk for c in self.covers}
        self.wait_mock.assert_called()

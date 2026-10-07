"""
Codex's own doctor rows.

Each check reads the host or the database and answers with comicbox's row
shape. These pin the verdicts: what counts as a failure, a warning, and an
optional feature that is simply off.
"""

import os
import shutil
from pathlib import Path
from typing import override
from unittest.mock import patch

from comicbox.doctor import Status
from cryptography.fernet import Fernet
from django.test import TestCase, override_settings

from codex.doctor import checks
from codex.doctor.checks import (
    check_config_dir,
    check_credentials,
    check_database,
    check_libraries,
    check_watcher,
)
from codex.librarian.fs.mounted import DOCKER_UNMOUNTED_FN
from codex.models import ComicboxTaggingDefaults, Folder, Library
from tests.tmp_dirs import tmp_dir

_ROOT = tmp_dir("codex.tests.doctor_checks")


class _DoctorCheckTestCase(TestCase):
    """A fresh scratch directory per test."""

    @override
    def setUp(self) -> None:
        self.scratch = _ROOT / self._testMethodName  # pyright: ignore[reportUninitializedInstanceVariable]
        self.scratch.mkdir(parents=True, exist_ok=True)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(self.scratch, ignore_errors=True)

    def _library(self, name: str = "lib", *, comics: bool = True, **fields) -> Path:
        root = self.scratch / name
        root.mkdir(exist_ok=True)
        if comics:
            (root / "a.cbz").write_bytes(b"")
        Library.objects.create(path=str(root), **fields)
        return root


class DatabaseCheckTests(TestCase):
    """The test database is the same engine the server runs on."""

    def test_reports_the_engine(self) -> None:
        (row,) = check_database()
        assert row.name == "database"
        assert str(row.found).startswith("sqlite ")
        # FTS5 is what the search index is built on; the suite needs it too.
        assert row.status is not Status.MISSING
        assert "fts5" in row.detail


class ConfigDirCheckTests(_DoctorCheckTestCase):
    """Writable with room is OK; unwritable is a failure."""

    def test_writable_with_room(self) -> None:
        with patch.object(checks, "CONFIG_PATH", self.scratch):
            (row,) = check_config_dir()
        assert row.status is Status.OK
        assert row.found == self.scratch
        assert "free" in row.detail

    def test_low_disk_warns(self) -> None:
        with (
            patch.object(checks, "CONFIG_PATH", self.scratch),
            patch.object(checks, "_LOW_DISK_BYTES", 1 << 62),
        ):
            (row,) = check_config_dir()
        assert row.status is Status.WARN
        assert "free some space" in row.fix

    def test_unwritable_is_misconfigured(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root writes anywhere")
        self.scratch.chmod(0o500)
        try:
            with patch.object(checks, "CONFIG_PATH", self.scratch):
                (row,) = check_config_dir()
        finally:
            self.scratch.chmod(0o700)
        assert row.status is Status.MISCONFIGURED
        assert "PUID" in row.fix


class LibrariesCheckTests(_DoctorCheckTestCase):
    """One row per library root, in path order."""

    def test_no_libraries_is_off(self) -> None:
        (row,) = check_libraries()
        assert row.status is Status.OFF
        assert "Libraries tab" in row.fix

    def test_a_readable_writable_library(self) -> None:
        root = self._library()
        (row,) = check_libraries()
        assert row.status is Status.OK
        assert row.found == root
        assert row.detail == "readable · writable"

    def test_read_only_is_not_asked_to_be_writable(self) -> None:
        self._library(read_only=True)
        (row,) = check_libraries()
        assert row.status is Status.OK
        assert row.detail == "readable · read only"

    def test_unwritable_warns_about_tag_writes(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root writes anywhere")
        root = self._library()
        root.chmod(0o500)
        try:
            (row,) = check_libraries()
        finally:
            root.chmod(0o700)
        assert row.status is Status.WARN
        assert "tag writes" in row.detail
        assert "read only" in row.fix

    def test_missing_root(self) -> None:
        Library.objects.create(path=str(self.scratch / "gone"))
        (row,) = check_libraries()
        assert row.status is Status.MISSING
        assert "deleted" in row.detail

    def test_unmounted_docker_volume(self) -> None:
        root = self._library(comics=False)
        (root / DOCKER_UNMOUNTED_FN).touch()
        (row,) = check_libraries()
        assert row.status is Status.MISCONFIGURED
        assert "bind mount" in row.fix

    def test_empty_root_warns(self) -> None:
        self._library(comics=False)
        (row,) = check_libraries()
        assert row.status is Status.WARN
        assert "empty" in row.detail

    def test_rows_follow_path_order(self) -> None:
        self._library("b")
        self._library("a")
        rows = list(check_libraries())
        assert [row.found for row in rows] == [self.scratch / "a", self.scratch / "b"]


class WatcherCheckTests(_DoctorCheckTestCase):
    """Folder count against the kernel's inotify watch limit, on Linux."""

    def _watched_library(self, folders: int) -> None:
        root = self._library()
        library = Library.objects.get(path=str(root))
        for index in range(folders):
            # Folder rows stat their path on save, so the directory must exist.
            (root / str(index)).mkdir()
            Folder.objects.create(
                library=library, path=f"{root}/{index}", name=str(index)
            )

    def _limits(self, max_watches: int) -> Path:
        inotify = self.scratch / "inotify"
        inotify.mkdir()
        (inotify / "max_user_watches").write_text(f"{max_watches}\n")
        return inotify

    def test_no_watched_libraries_is_off(self) -> None:
        self._library(events=False)
        (row,) = check_watcher()
        assert row.status is Status.OFF

    def test_other_platforms_have_no_limit(self) -> None:
        self._watched_library(3)
        with patch.object(checks, "_HAS_INOTIFY", new=False):
            (row,) = check_watcher()
        assert row.status is Status.OK
        assert row.found == "4 folders"

    def test_within_the_limit(self) -> None:
        self._watched_library(3)
        inotify = self._limits(8192)
        with (
            patch.object(checks, "_HAS_INOTIFY", new=True),
            patch.object(checks, "_INOTIFY_DIR", inotify),
        ):
            (row,) = check_watcher()
        assert row.status is Status.OK
        assert row.detail == "inotify allows 8192"

    def test_near_the_limit_warns(self) -> None:
        self._watched_library(9)
        inotify = self._limits(12)
        with (
            patch.object(checks, "_HAS_INOTIFY", new=True),
            patch.object(checks, "_INOTIFY_DIR", inotify),
        ):
            (row,) = check_watcher()
        assert row.status is Status.WARN
        assert row.fix.startswith("sysctl fs.inotify.max_user_watches=524288 on ")

    def test_over_the_limit_is_misconfigured(self) -> None:
        self._watched_library(9)
        inotify = self._limits(4)
        with (
            patch.object(checks, "_HAS_INOTIFY", new=True),
            patch.object(checks, "_INOTIFY_DIR", inotify),
            patch.object(checks, "is_docker", return_value=True),
        ):
            (row,) = check_watcher()
        assert row.status is Status.MISCONFIGURED
        assert row.fix.endswith(" on the Docker host")

    def test_unreadable_limit_warns(self) -> None:
        self._watched_library(1)
        with (
            patch.object(checks, "_HAS_INOTIFY", new=True),
            patch.object(checks, "_INOTIFY_DIR", self.scratch / "nope"),
        ):
            (row,) = check_watcher()
        assert row.status is Status.WARN
        assert "unreadable" in row.detail


class CredentialsCheckTests(TestCase):
    """Stored credentials must decrypt with the key file in the config dir."""

    def test_none_stored_is_off(self) -> None:
        ComicboxTaggingDefaults.objects.update_or_create(pk=1)
        (row,) = check_credentials()
        assert row.status is Status.OFF

    def test_stored_credentials_decrypt(self) -> None:
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"metron_key": "token", "comicvine_key": "cv"}
        )
        (row,) = check_credentials()
        assert row.status is Status.OK
        assert row.found == "metron_key, comicvine_key"

    def test_a_changed_key_file_is_misconfigured(self) -> None:
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"metron_key": "token", "metron_user": "u"}
        )
        with override_settings(FIELD_ENCRYPTION_KEY=Fernet.generate_key()):
            (row,) = check_credentials()
        assert row.status is Status.MISCONFIGURED
        assert row.found == "metron_key, metron_user"
        assert "Tagging tab" in row.fix

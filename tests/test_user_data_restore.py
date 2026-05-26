"""Round-trip restore tests: main DB → sidecar → wipe → restore."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import Group, User
from django.test import TestCase

from codex.models import (
    Bookmark,
    Comic,
    Favorite,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.models.admin import AdminFlag, Timestamp
from codex.user_data.dump import dump_user_data
from codex.user_data.restore import restore
from codex.user_data.store import SidecarStore, reset_store_for_tests

_TMP_DIR: Final = Path("/tmp/codex.tests.sidecar.restore")  # noqa: S108
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_SEED_BOOKMARK_PAGE: Final = 7
_SEED_FAVORITES_COUNT: Final = 2


class _SidecarRestoreCase(TestCase):
    """Shared setup: install a clean sidecar pointed at a temp file."""

    @override
    def setUp(self) -> None:
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        (_TMP_DIR / "config").mkdir(exist_ok=True)
        (_TMP_DIR / "comics").mkdir(exist_ok=True)
        sidecar_path = _TMP_DIR / "config" / "user_data.sqlite"
        for suffix in ("", "-wal", "-shm"):
            sidecar_path.with_name(sidecar_path.name + suffix).unlink(missing_ok=True)
        self.sidecar_path = sidecar_path  # pyright: ignore[reportUninitializedInstanceVariable]
        self.store = SidecarStore(sidecar_path)  # pyright: ignore[reportUninitializedInstanceVariable]
        from codex.user_data import store as store_module

        store_module._store = self.store  # noqa: SLF001

    @override
    def tearDown(self) -> None:
        self.store.close()
        reset_store_for_tests(None)
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _snapshot_sidecar(self) -> Path:
        """
        Dump the main-DB state to the sidecar; return a frozen copy.

        Subsequent main-DB deletes won't touch the sidecar (we no longer
        mirror via signals); the snapshot file is the artifact we restore
        from to simulate "main DB lost, sidecar intact."
        """
        dump_user_data()
        # Force any pending WAL writes to flush.
        self.store.connection().execute("PRAGMA wal_checkpoint(FULL)")
        snapshot = _TMP_DIR / "config" / "snapshot.sqlite"
        snapshot.unlink(missing_ok=True)
        # ``sqlite3.backup`` produces a consistent copy under load.
        with sqlite3.connect(snapshot) as dst:
            self.store.connection().backup(dst)
        return snapshot


class RestoreRoundTripTests(_SidecarRestoreCase):
    """Write → wipe → restore → compare."""

    def _seed_main_db(self) -> dict:
        """Create a representative set of user-data rows in the main DB."""
        user = User.objects.create_user(
            username="alice", password=_TEST_PASSWORD, email="a@x"
        )
        editors = Group.objects.create(name="editors")
        user.groups.add(editors)

        comic_path = _TMP_DIR / "comics" / "x.cbz"
        comic_path.touch()
        library = Library.objects.create(path=str(_TMP_DIR / "comics"))
        library.groups.add(editors)

        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        comic = Comic.objects.create(
            library=library,
            path=str(comic_path),
            issue_number=1,
            name="x",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=1,
        )
        Bookmark.objects.create(
            user=user, comic=comic, page=_SEED_BOOKMARK_PAGE, finished=True
        )
        Favorite.objects.create(user=user, group="p", target_id=publisher.pk)
        Favorite.objects.create(user=user, group="s", target_id=series.pk)
        # update_or_create rather than create — other suites' setUpTestData
        # calls into codex_init() can leak seeded AdminFlag/Timestamp rows
        # past TestCase's per-test rollback.
        AdminFlag.objects.update_or_create(
            key="AU", defaults={"on": False, "value": "off"}
        )
        # The API key moved off Timestamp to AdminFlag (key ``AK``).
        # Seed both the moved row and the codex-version Timestamp row
        # to exercise both code paths in the restore.
        AdminFlag.objects.update_or_create(
            key="AK", defaults={"on": True, "value": "test-key-abc"}
        )
        Timestamp.objects.update_or_create(key="VR", defaults={"value": "1.2.3"})
        return {
            "user": user,
            "comic": comic,
            "publisher": publisher,
            "series": series,
            "library": library,
            "editors": editors,
            "comic_path": str(comic_path),
        }

    def test_round_trip_restores_users_and_groups(self) -> None:
        self._seed_main_db()
        snapshot = self._snapshot_sidecar()
        User.objects.filter(username="alice").delete()
        Group.objects.filter(name="editors").delete()

        report = restore(sidecar_path=snapshot)
        assert report.written.get("users", 0) >= 1
        assert report.written.get("groups", 0) >= 1
        user = User.objects.get(username="alice")
        assert user.email == "a@x"
        assert Group.objects.filter(name="editors").exists()
        assert user.groups.filter(name="editors").exists()

    def test_round_trip_restores_bookmarks(self) -> None:
        seed = self._seed_main_db()
        snapshot = self._snapshot_sidecar()
        Bookmark.objects.all().delete()
        assert not Bookmark.objects.exists()

        report = restore(sidecar_path=snapshot)
        assert report.written.get("bookmarks", 0) >= 1
        bm = Bookmark.objects.get(user=seed["user"], comic=seed["comic"])
        assert bm.page == _SEED_BOOKMARK_PAGE
        assert bm.finished is True

    def test_round_trip_restores_favorites(self) -> None:
        seed = self._seed_main_db()
        snapshot = self._snapshot_sidecar()
        Favorite.objects.all().delete()

        report = restore(sidecar_path=snapshot)
        assert report.written.get("favorites", 0) >= _SEED_FAVORITES_COUNT
        Favorite.objects.get(
            user=seed["user"], group="p", target_id=seed["publisher"].pk
        )
        Favorite.objects.get(user=seed["user"], group="s", target_id=seed["series"].pk)

    def test_restore_logs_unmatched_comic(self) -> None:
        seed = self._seed_main_db()
        snapshot = self._snapshot_sidecar()
        # Snapshot captured the bookmark + its comic_path. Deleting the
        # comic from the main DB doesn't touch the snapshot file; on
        # restore the comic_path won't resolve and the bookmark is
        # logged as unmatched.
        seed["comic"].delete()

        report = restore(sidecar_path=snapshot)
        assert report.skipped.get("bookmarks", 0) >= 1
        assert any("missing comic" in line for line in report.unmatched_log)

    def test_dry_run_writes_nothing(self) -> None:
        self._seed_main_db()
        snapshot = self._snapshot_sidecar()
        user_count = User.objects.count()
        AdminFlag.objects.all().delete()
        report = restore(sidecar_path=snapshot, dry_run=True)
        # Counts populated…
        assert report.written.get("admin_flags", 0) >= 1
        # …but no rows actually written.
        assert AdminFlag.objects.filter(key="AU").exists() is False
        assert User.objects.count() == user_count

    def test_round_trip_restores_admin_flag_and_timestamp(self) -> None:
        self._seed_main_db()
        snapshot = self._snapshot_sidecar()
        AdminFlag.objects.filter(key="AU").delete()
        AdminFlag.objects.filter(key="AK").delete()
        Timestamp.objects.filter(key="VR").delete()

        report = restore(sidecar_path=snapshot)
        assert report.written.get("admin_flags", 0) >= 1
        assert report.written.get("timestamps", 0) >= 1
        flag = AdminFlag.objects.get(key="AU")
        assert flag.on is False
        assert flag.value == "off"
        api_key_flag = AdminFlag.objects.get(key="AK")
        assert api_key_flag.value == "test-key-abc"
        ts = Timestamp.objects.get(key="VR")
        assert ts.value == "1.2.3"

    def test_restore_is_idempotent(self) -> None:
        self._seed_main_db()
        snapshot = self._snapshot_sidecar()
        first = restore(sidecar_path=snapshot)
        second = restore(sidecar_path=snapshot)
        assert first.written
        assert second.written
        # Still one row per key.
        assert User.objects.filter(username="alice").count() == 1
        assert AdminFlag.objects.filter(key="AU").count() == 1

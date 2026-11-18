"""Round-trip restore tests: main DB → sidecar → wipe → restore."""

from __future__ import annotations

import base64
import shutil
import sqlite3
from typing import TYPE_CHECKING, Final, override
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.choices.admin import AdminFlagChoices
from codex.choices.api_key import ApiKeyScope
from codex.models import (
    Bookmark,
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Shelf,
    ShelfItem,
    Volume,
)
from codex.models.admin import AdminFlag, Timestamp
from codex.models.api_key import RevokedApiKey, UserApiKey
from codex.startup import init_admin_flags
from codex.user_data.dump import dump_user_data
from codex.user_data.restore import restore
from codex.user_data.store import SidecarStore, reset_store_for_tests
from tests.tmp_dirs import tmp_dir

if TYPE_CHECKING:
    from pathlib import Path

_TMP_DIR: Final = tmp_dir("codex.tests.sidecar.restore")
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_SEED_BOOKMARK_PAGE: Final = 7
_SEED_SHELF_ITEMS_COUNT: Final = 2
_SEED_SHELF_NAME: Final = "Want to Read"
_HTTP_OK: Final = 200


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
        shelf = Shelf.objects.create(user=user, name=_SEED_SHELF_NAME)
        ShelfItem.objects.create(
            shelf=shelf, collection="publishers", target_id=publisher.pk
        )
        ShelfItem.objects.create(shelf=shelf, collection="series", target_id=series.pk)
        # An empty shelf must survive the round trip too.
        Shelf.objects.create(user=user, name="Empty")
        # update_or_create rather than create — other suites' setUpTestData
        # calls into codex_init() can leak seeded AdminFlag/Timestamp rows
        # past TestCase's per-test rollback.
        AdminFlag.objects.update_or_create(
            key="AU", defaults={"on": False, "value": "off"}
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

    def test_round_trip_restores_shelves(self) -> None:
        seed = self._seed_main_db()
        snapshot = self._snapshot_sidecar()
        Shelf.objects.all().delete()
        assert not ShelfItem.objects.exists()

        report = restore(sidecar_path=snapshot)
        assert report.written.get("shelf_items", 0) >= _SEED_SHELF_ITEMS_COUNT
        shelf = Shelf.objects.get(user=seed["user"], name=_SEED_SHELF_NAME)
        ShelfItem.objects.get(
            shelf=shelf, collection="publishers", target_id=seed["publisher"].pk
        )
        ShelfItem.objects.get(
            shelf=shelf, collection="series", target_id=seed["series"].pk
        )
        assert not ShelfItem.objects.filter(
            shelf__user=seed["user"], shelf__name="Empty"
        ).exists()

    def test_round_trip_restores_shelves_filter(self) -> None:
        """A stored shelves filter comes back pointing at the restored shelf."""
        from codex.models.settings import (
            SettingsBrowser,
            SettingsBrowserFilters,
            SettingsBrowserShow,
        )

        seed = self._seed_main_db()
        shelf = Shelf.objects.get(user=seed["user"], name=_SEED_SHELF_NAME)
        show, _ = SettingsBrowserShow.objects.get_or_create()
        browser = SettingsBrowser.objects.create(user=seed["user"], show=show)
        SettingsBrowserFilters.objects.create(browser=browser, shelves=[shelf.pk])
        snapshot = self._snapshot_sidecar()
        SettingsBrowser.objects.all().delete()
        Shelf.objects.all().delete()

        restore(sidecar_path=snapshot)

        restored = Shelf.objects.get(user=seed["user"], name=_SEED_SHELF_NAME)
        filters = SettingsBrowserFilters.objects.get(browser__user=seed["user"])
        assert filters.shelves == [restored.pk]

    def test_pre_shelves_backup_restores_favorites_onto_a_shelf(self) -> None:
        """A backup with a ``favorites`` table lands on a "Favorites" shelf."""
        from codex.models.settings import (
            SettingsBrowser,
            SettingsBrowserFilters,
            SettingsBrowserShow,
        )

        seed = self._seed_main_db()
        show, _ = SettingsBrowserShow.objects.get_or_create()
        browser = SettingsBrowser.objects.create(
            user=seed["user"], show=show, order_by="shelved"
        )
        SettingsBrowserFilters.objects.create(browser=browser)
        snapshot = self._snapshot_sidecar()
        # Rewrite the snapshot into the shape a pre-shelves codex wrote:
        # a favorites table, a favorite flag and the favorite sort key.
        with sqlite3.connect(snapshot) as conn:
            conn.executescript(
                """
                CREATE TABLE favorites (
                    username TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    identifier_json TEXT NOT NULL,
                    updated_at TEXT,
                    PRIMARY KEY (username, collection, identifier_json)
                );
                INSERT INTO favorites
                    SELECT username, collection, identifier_json, updated_at
                    FROM shelf_items;
                DROP TABLE shelf_items;
                DROP TABLE shelves;
                ALTER TABLE settings_filters
                    ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0;
                UPDATE settings_filters SET favorite = 1;
                ALTER TABLE settings_filters DROP COLUMN shelves;
                """
            )
            conn.execute("UPDATE settings_browser SET order_by = 'favorite'")
        SettingsBrowser.objects.all().delete()
        Shelf.objects.all().delete()

        report = restore(sidecar_path=snapshot)

        assert report.written.get("favorites", 0) >= _SEED_SHELF_ITEMS_COUNT
        shelf = Shelf.objects.get(user=seed["user"])
        assert shelf.name == "Favorites"
        assert ShelfItem.objects.filter(shelf=shelf).count() == _SEED_SHELF_ITEMS_COUNT
        restored = SettingsBrowser.objects.get(user=seed["user"])
        assert restored.order_by == "shelved"
        filters = SettingsBrowserFilters.objects.get(browser=restored)
        assert filters.shelves == [shelf.pk]

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
        Timestamp.objects.filter(key="VR").delete()

        report = restore(sidecar_path=snapshot)
        assert report.written.get("admin_flags", 0) >= 1
        assert report.written.get("timestamps", 0) >= 1
        flag = AdminFlag.objects.get(key="AU")
        assert flag.on is False
        assert flag.value == "off"
        ts = Timestamp.objects.get(key="VR")
        assert ts.value == "1.2.3"

    def test_round_trip_restores_settings_browser_show(self) -> None:
        from codex.models.settings import SettingsBrowser, SettingsBrowserShow

        user = User.objects.create_user(username="alice", password=_TEST_PASSWORD)
        show = SettingsBrowserShow.objects.create(
            publishers=False, imprints=True, series=False, volumes=True
        )
        SettingsBrowser.objects.create(user=user, show=show)
        snapshot = self._snapshot_sidecar()

        # Drop the browser first (PROTECT), then the shared show row, so
        # restore must reconstruct both via get_or_create kwargs.
        SettingsBrowser.objects.all().delete()
        SettingsBrowserShow.objects.all().delete()

        report = restore(sidecar_path=snapshot)
        assert report.written.get("settings_browser", 0) >= 1
        browser = SettingsBrowser.objects.get(user=user)
        assert browser.show.publishers is False
        assert browser.show.imprints is True
        assert browser.show.series is False
        assert browser.show.volumes is True

    def test_round_trip_restores_reprints_filter(self) -> None:
        """
        A reprints filter survives a rebuild that renumbers its PKs.

        The sidecar stores tag filters by name, and ``Reprint`` is the
        only tag model whose name lives on ``series_name`` rather than
        ``name`` — a dump that reached for ``name`` would raise.
        """
        from codex.models.named import Reprint
        from codex.models.settings import (
            SettingsBrowser,
            SettingsBrowserFilters,
            SettingsBrowserShow,
        )

        user = User.objects.create_user(username="alice", password=_TEST_PASSWORD)
        show, _ = SettingsBrowserShow.objects.get_or_create()
        browser = SettingsBrowser.objects.create(user=user, show=show)
        reprint = Reprint.objects.create(
            series_name="Kapitän Wissenschaft", language="de"
        )
        SettingsBrowserFilters.objects.create(browser=browser, reprints=[reprint.pk])
        snapshot = self._snapshot_sidecar()

        # Rebuilding the library re-creates the tag row under a new PK,
        # which is the whole reason the sidecar keys on names.
        SettingsBrowser.objects.all().delete()
        reprint.delete()
        rebuilt = Reprint.objects.create(
            series_name="Kapitän Wissenschaft", language="de"
        )
        assert rebuilt.pk != reprint.pk

        restore(sidecar_path=snapshot)
        filters = SettingsBrowserFilters.objects.get(browser__user=user)
        assert filters.reprints == [rebuilt.pk]

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


class ApiKeyRestoreTests(_SidecarRestoreCase):
    """Keys come back as hashes and still log in."""

    def _seed(self) -> None:
        init_admin_flags()
        AdminFlag.objects.filter(key=AdminFlagChoices.NON_USERS.value).update(on=False)
        self.reader = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="alice", password=_TEST_PASSWORD
        )
        self.admin = User.objects.create_superuser(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="boss", email="", password=_TEST_PASSWORD
        )
        self.device, self.device_key = UserApiKey.create_for_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            self.reader, "Kobo"
        )
        self.stats, self.stats_key = UserApiKey.create_for_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            self.admin, "Grafana", ApiKeyScope.STATS
        )
        cache.clear()

    @staticmethod
    def _logs_in(path: str, auth: str) -> bool:
        # The stats are counted on another thread, which the test
        # transaction locks out; only the credential is under test.
        with patch("codex.views.admin.stats.CodexStats") as stats:
            stats.return_value.get.return_value = {}
            response = Client().get(path, HTTP_AUTHORIZATION=auth)
        return response.status_code == _HTTP_OK

    def _assert_keys_log_in(self) -> None:
        basic = base64.b64encode(f"alice:{self.device_key}".encode()).decode()
        assert self._logs_in("/opds/v2.0/", f"Basic {basic}")
        assert self._logs_in("/api/v4/admin/stats", f"Bearer {self.stats_key}")

    def test_keys_round_trip_and_still_log_in(self) -> None:
        self._seed()
        created = self.device.created_at
        snapshot = self._snapshot_sidecar()
        UserApiKey.objects.all().delete()

        report = restore(sidecar_path=snapshot)

        # Keys the backup has and the database doesn't are re-created: maybe
        # revoked since the backup, so they get their own line.
        assert report.written.get("api_keys_recreated") == 2  # noqa: PLR2004
        assert "api_keys" not in report.written
        device = UserApiKey.objects.get(user=self.reader)
        assert (device.name, device.scope, device.digest) == (
            "Kobo",
            ApiKeyScope.DEVICE,
            self.device.digest,
        )
        assert device.created_at == created
        assert UserApiKey.objects.get(user=self.admin).scope == ApiKeyScope.STATS
        self._assert_keys_log_in()

    def test_a_second_restore_adds_nothing(self) -> None:
        self._seed()
        snapshot = self._snapshot_sidecar()
        restore(sidecar_path=snapshot)
        report = restore(sidecar_path=snapshot)
        assert UserApiKey.objects.count() == 2  # noqa: PLR2004
        # Keys still here are ordinary rows, not re-created ones.
        assert report.written.get("api_keys") == 2  # noqa: PLR2004
        assert "api_keys_recreated" not in report.written

    def _restore_after_revoking_the_device_key(self):
        self._seed()
        snapshot = self._snapshot_sidecar()
        client = Client()
        client.force_login(self.reader)
        response = client.delete(f"/api/v4/auth/keys/{self.device.pk}")
        assert response.status_code == 204  # noqa: PLR2004
        return restore(sidecar_path=snapshot)

    def test_a_key_revoked_after_the_backup_stays_revoked(self) -> None:
        report = self._restore_after_revoking_the_device_key()

        assert not UserApiKey.objects.filter(digest=self.device.digest).exists()
        assert RevokedApiKey.objects.filter(digest=self.device.digest).exists()
        basic = base64.b64encode(f"alice:{self.device_key}".encode()).decode()
        assert not self._logs_in("/opds/v2.0/", f"Basic {basic}")
        # The key that was never revoked is still an ordinary row.
        assert report.written.get("api_keys") == 1
        assert "api_keys_recreated" not in report.written

    def test_a_revoked_key_is_reported_skipped_with_its_reason(self) -> None:
        report = self._restore_after_revoking_the_device_key()

        assert report.skipped.get("api_keys") == 1
        reasons = [line for line in report.unmatched_log if "api_keys" in line]
        reason = "key 'Kobo' of user 'alice' was revoked after this backup"
        assert reasons == [f"[api_keys] {reason}; not re-created"]

    def test_missing_user_is_skipped(self) -> None:
        self._seed()
        snapshot = self._snapshot_sidecar()
        with sqlite3.connect(snapshot) as conn:
            conn.execute("DELETE FROM users WHERE username = 'alice'")
        self.reader.delete()

        report = restore(sidecar_path=snapshot)

        assert report.skipped.get("api_keys") == 1
        assert not UserApiKey.objects.filter(name="Kobo").exists()

    def test_an_existing_key_of_the_same_name_is_kept(self) -> None:
        self._seed()
        snapshot = self._snapshot_sidecar()
        self.device.delete()
        replacement, _ = UserApiKey.create_for_user(self.reader, "Kobo")

        report = restore(sidecar_path=snapshot)

        assert report.skipped.get("api_keys") == 1
        assert list(UserApiKey.objects.filter(user=self.reader)) == [replacement]

    def test_a_backup_without_keys_restores(self) -> None:
        self._seed()
        snapshot = self._snapshot_sidecar()
        with sqlite3.connect(snapshot) as conn:
            conn.execute("DROP TABLE api_keys")
        UserApiKey.objects.all().delete()

        report = restore(sidecar_path=snapshot)

        assert report.written.get("users")
        assert not UserApiKey.objects.exists()

    def test_an_old_server_api_key_is_not_restored(self) -> None:
        """The server-wide Stats API key was revoked: a backup can't revive it."""
        self._seed()
        old_key = "legacy-server-api-key"
        snapshot = self._snapshot_sidecar()
        with sqlite3.connect(snapshot) as conn:
            conn.execute("DROP TABLE api_keys")
            conn.execute(
                "INSERT INTO admin_flags (key, on_flag, value) VALUES ('AK', 1, ?)",
                (old_key,),
            )
        UserApiKey.objects.all().delete()

        restore(sidecar_path=snapshot)

        assert not UserApiKey.objects.exists()
        assert not AdminFlag.objects.filter(key="AK").exists()
        assert not self._logs_in("/api/v4/admin/stats", f"Bearer {old_key}")


class SettingsDefaultsRestoreTests(_SidecarRestoreCase):
    """The site defaults singleton round-trips; a legacy BG flag maps onto it."""

    _COLUMNS: Final = {"folders": ["cover", "name", "child_count"]}

    def test_round_trip_restores_settings_defaults(self) -> None:
        from codex.models.admin import SettingsDefaults

        SettingsDefaults.objects.update_or_create(
            pk=1,
            defaults={
                "top_collection": "arcs",
                "view_mode": "table",
                "bookmark": "UNREAD",
                "table_columns": self._COLUMNS,
                "fit_to": "H",
                "page_transition": False,
            },
        )
        snapshot = self._snapshot_sidecar()
        SettingsDefaults.objects.all().delete()

        report = restore(sidecar_path=snapshot)

        assert report.written.get("settings_defaults") == 1
        row = SettingsDefaults.objects.get(pk=1)
        assert row.top_collection == "arcs"
        assert row.view_mode == "table"
        assert row.bookmark == "UNREAD"
        assert row.table_columns == self._COLUMNS
        assert row.fit_to == "H"
        assert row.page_transition is False

    def _legacy_snapshot(self, *, bg_value: str, fv_on: bool) -> Path:
        """Snapshot a pre-SettingsDefaults backup: a BG flag, no singleton row."""
        snapshot = self._snapshot_sidecar()
        with sqlite3.connect(snapshot) as conn:
            conn.execute("DELETE FROM settings_defaults")
            conn.execute("DELETE FROM admin_flags WHERE key IN ('BG', 'FV')")
            conn.executemany(
                "INSERT INTO admin_flags (key, on_flag, value) VALUES (?, ?, ?)",
                (("BG", 1, bg_value), ("FV", int(fv_on), "")),
            )
        return snapshot

    def test_legacy_backup_maps_bg_onto_top_collection(self) -> None:
        from codex.models.admin import SettingsDefaults

        snapshot = self._legacy_snapshot(bg_value="folders", fv_on=True)
        SettingsDefaults.objects.filter(pk=1).update(view_mode="table")

        restore(sidecar_path=snapshot)

        row = SettingsDefaults.objects.get(pk=1)
        assert row.top_collection == "folders"
        # Only the top collection comes from a legacy backup.
        assert row.view_mode == "table"
        assert not AdminFlag.objects.filter(key="BG").exists()

    def test_legacy_backup_folders_without_folder_view(self) -> None:
        from codex.models.admin import SettingsDefaults

        snapshot = self._legacy_snapshot(bg_value="folders", fv_on=False)
        restore(sidecar_path=snapshot)
        assert SettingsDefaults.objects.get(pk=1).top_collection == "publishers"


class OverlappingLibraryRestoreTests(_SidecarRestoreCase):
    """
    The sidecar keys user data on a path, which two libraries can share.

    ``WatchedPath`` is unique on ``(library, path)``, so nested library
    roots hold one file under two Comic rows. The sidecar records no
    library, so a restore that resolved the path to an arbitrary single
    row dropped the user's reading position in whichever library they
    actually browse.
    """

    def _seed_overlapping_libraries(self) -> dict:
        """One file on disk, tracked by an outer and an inner library."""
        user = User.objects.create_user(username="alice", password=_TEST_PASSWORD)
        inner_dir = _TMP_DIR / "comics" / "inner"
        inner_dir.mkdir(parents=True, exist_ok=True)
        comic_path = inner_dir / "x.cbz"
        comic_path.touch()
        outer = Library.objects.create(path=str(_TMP_DIR / "comics"))
        inner = Library.objects.create(path=str(inner_dir))

        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        comics = [
            Comic.objects.create(
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
            for library in (outer, inner)
        ]
        folders = [
            Folder.objects.create(
                library=library, path=str(inner_dir), name=inner_dir.name
            )
            for library in (outer, inner)
        ]
        return {"user": user, "comics": comics, "folders": folders}

    def test_bookmark_restores_into_every_overlapping_library(self) -> None:
        seed = self._seed_overlapping_libraries()
        Bookmark.objects.create(
            user=seed["user"],
            comic=seed["comics"][0],
            page=_SEED_BOOKMARK_PAGE,
            finished=True,
        )
        snapshot = self._snapshot_sidecar()
        Bookmark.objects.all().delete()

        report = restore(sidecar_path=snapshot)

        assert report.written.get("bookmarks", 0) >= 1
        for comic in seed["comics"]:
            bookmark = Bookmark.objects.get(user=seed["user"], comic=comic)
            assert bookmark.page == _SEED_BOOKMARK_PAGE
            assert bookmark.finished is True

    def test_shelved_folder_restores_into_every_overlapping_library(self) -> None:
        seed = self._seed_overlapping_libraries()
        shelf = Shelf.objects.create(user=seed["user"], name="Folders")
        ShelfItem.objects.create(
            shelf=shelf, collection="folders", target_id=seed["folders"][0].pk
        )
        snapshot = self._snapshot_sidecar()
        Shelf.objects.all().delete()

        report = restore(sidecar_path=snapshot)

        assert report.written.get("shelf_items", 0) >= 1
        for folder in seed["folders"]:
            assert ShelfItem.objects.filter(
                shelf__user=seed["user"], collection="folders", target_id=folder.pk
            ).exists()

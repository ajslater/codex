"""End-to-end tests for sidecar signal mirroring."""

from __future__ import annotations

import json
import shutil
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
from codex.models.auth import UserAuth
from codex.models.settings import (
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserLastRoute,
    SettingsBrowserShow,
)
from codex.user_data.backfill import run_backfill
from codex.user_data.store import SidecarStore, reset_store_for_tests

_TMP_DIR: Final = Path("/tmp/codex.tests.sidecar.signals")  # noqa: S108
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_BOOKMARK_PAGE: Final = 5
_LAST_ROUTE_PAGE: Final = 2


class _SidecarTestCase(TestCase):
    """Common: install a clean sidecar pointed at a temp file."""

    @override
    def setUp(self) -> None:
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        for sub in ("comics", "config"):
            (_TMP_DIR / sub).mkdir(exist_ok=True, parents=True)
        sidecar_path = _TMP_DIR / "config" / "user_data.sqlite"
        for suffix in ("", "-wal", "-shm"):
            sidecar_path.with_name(sidecar_path.name + suffix).unlink(missing_ok=True)
        self.store = SidecarStore(sidecar_path)  # pyright: ignore[reportUninitializedInstanceVariable]
        # Install our test store as the process-wide singleton so signal
        # handlers pick it up.
        from codex.user_data import store as store_module

        store_module._store = self.store  # noqa: SLF001

    @override
    def tearDown(self) -> None:
        self.store.close()
        reset_store_for_tests(None)
        shutil.rmtree(_TMP_DIR, ignore_errors=True)


class UserBookmarkFavoriteSignalTests(_SidecarTestCase):
    """User, Bookmark, Favorite — the high-traffic user-data writes."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="alice", password=_TEST_PASSWORD, email="a@x"
        )
        comic_path = _TMP_DIR / "comics" / "x.cbz"
        comic_path.touch()
        library = Library.objects.create(path=str(_TMP_DIR / "comics"))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        self.comic = Comic.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=library,
            path=comic_path,
            issue_number=1,
            name="x",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=1,
        )
        self.publisher = publisher  # pyright: ignore[reportUninitializedInstanceVariable]

    def test_user_create_mirrors_to_sidecar(self) -> None:
        row = self.store.fetchall("users")[0]
        # The signal-created user from setUp() is in the sidecar.
        assert row["username"] == "alice"
        assert row["email"] == "a@x"

    def test_user_update_mirrors_changes(self) -> None:
        self.user.email = "a@y"
        self.user.save()
        rows = self.store.fetchall("users")
        match = next(r for r in rows if r["username"] == "alice")
        assert match["email"] == "a@y"

    def test_user_delete_cascades_in_sidecar(self) -> None:
        username = self.user.username
        Bookmark.objects.create(user=self.user, comic=self.comic, page=3)
        self.user.delete()
        assert (
            self.store.connection()
            .execute("SELECT 1 FROM users WHERE username=?", (username,))
            .fetchone()
            is None
        )
        # Cascade also drops bookmarks for that user.
        assert (
            self.store.connection()
            .execute("SELECT 1 FROM bookmarks WHERE username=?", (username,))
            .fetchone()
            is None
        )

    def test_bookmark_save_writes_username_and_comic_path(self) -> None:
        Bookmark.objects.create(user=self.user, comic=self.comic, page=_BOOKMARK_PAGE)
        rows = self.store.fetchall("bookmarks")
        assert len(rows) == 1
        row = rows[0]
        assert row["username"] == "alice"
        assert row["comic_path"] == str(self.comic.path)
        assert row["page"] == _BOOKMARK_PAGE

    def test_anonymous_bookmark_is_skipped(self) -> None:
        # Anonymous (session-only) bookmarks have user=None — they must
        # not land in the sidecar.
        from django.contrib.sessions.models import Session
        from django.utils import timezone

        session = Session.objects.create(
            session_key="abc123",
            session_data="",
            expire_date=timezone.now(),
        )
        Bookmark.objects.create(user=None, session=session, comic=self.comic, page=2)
        assert self.store.fetchall("bookmarks") == []

    def test_bookmark_delete_removes_sidecar_row(self) -> None:
        bm = Bookmark.objects.create(
            user=self.user, comic=self.comic, page=_BOOKMARK_PAGE
        )
        bm.delete()
        assert self.store.fetchall("bookmarks") == []

    def test_favorite_save_resolves_publisher_to_name_chain(self) -> None:
        Favorite.objects.create(user=self.user, group="p", target_id=self.publisher.pk)
        rows = self.store.fetchall("favorites")
        assert len(rows) == 1
        row = rows[0]
        assert row["username"] == "alice"
        assert row["group_char"] == "p"
        # Identifier is a JSON list ["p", publisher_name].
        decoded = json.loads(row["identifier_json"])
        assert decoded == ["p", "Pub"]

    def test_favorite_delete_removes_sidecar_row(self) -> None:
        fav = Favorite.objects.create(
            user=self.user, group="p", target_id=self.publisher.pk
        )
        fav.delete()
        assert self.store.fetchall("favorites") == []

    def test_publisher_delete_cascades_favorites_in_sidecar(self) -> None:
        Favorite.objects.create(user=self.user, group="p", target_id=self.publisher.pk)
        self.publisher.delete()
        assert self.store.fetchall("favorites") == []


class GroupAndLibrarySignalTests(_SidecarTestCase):
    """Group, Library, M2M memberships."""

    def test_group_save_mirrors_with_empty_permissions(self) -> None:
        Group.objects.create(name="editors")
        rows = self.store.fetchall("groups")
        match = next(r for r in rows if r["name"] == "editors")
        assert json.loads(match["permissions"]) == []
        assert match["exclude"] == 0

    def test_user_groups_m2m_add_and_remove(self) -> None:
        user = User.objects.create_user(username="bob", password=_TEST_PASSWORD)
        editors = Group.objects.create(name="editors")
        user.groups.add(editors)
        rows = self.store.fetchall("user_groups")
        assert any(
            r["username"] == "bob" and r["group_name"] == "editors" for r in rows
        )
        user.groups.remove(editors)
        rows = self.store.fetchall("user_groups")
        assert not any(
            r["username"] == "bob" and r["group_name"] == "editors" for r in rows
        )

    def test_library_save_and_groups_m2m(self) -> None:
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(_TMP_DIR))
        editors = Group.objects.create(name="editors")
        library.groups.add(editors)
        rows = self.store.fetchall("libraries")
        assert any(r["path"] == str(_TMP_DIR) for r in rows)
        rows = self.store.fetchall("library_groups")
        assert any(
            r["library_path"] == str(_TMP_DIR) and r["group_name"] == "editors"
            for r in rows
        )


class AdminFlagTimestampSignalTests(_SidecarTestCase):
    """AdminFlag and Timestamp — singleton-style rows keyed on ``key``."""

    def test_admin_flag_upsert(self) -> None:
        # Other test suites that call codex_init() can leave seeded
        # AdminFlag rows behind despite TestCase rollback — use
        # update_or_create so we exercise the signal on a known state.
        flag, _ = AdminFlag.objects.update_or_create(
            key="AU", defaults={"on": False, "value": "hi"}
        )
        rows = self.store.fetchall("admin_flags")
        match = next(r for r in rows if r["key"] == "AU")
        assert match["on_flag"] == 0
        assert match["value"] == "hi"
        flag.on = True
        flag.save()
        rows = self.store.fetchall("admin_flags")
        match = next(r for r in rows if r["key"] == "AU")
        assert match["on_flag"] == 1

    def test_admin_flag_delete(self) -> None:
        flag, _ = AdminFlag.objects.update_or_create(key="AU", defaults={"on": False})
        flag.delete()
        rows = self.store.fetchall("admin_flags")
        assert all(r["key"] != "AU" for r in rows)

    def test_timestamp_save(self) -> None:
        Timestamp.objects.update_or_create(key="AP", defaults={"version": "v1"})
        rows = self.store.fetchall("timestamps")
        match = next(r for r in rows if r["key"] == "AP")
        assert match["version"] == "v1"


class SettingsBrowserSignalTests(_SidecarTestCase):
    """Browser settings + filters + last-route mirror to three tables."""

    def test_browser_settings_full_round_trip(self) -> None:
        user = User.objects.create_user(username="alice", password=_TEST_PASSWORD)
        show, _ = SettingsBrowserShow.objects.get_or_create(
            p=True, i=False, s=True, v=False
        )
        browser = SettingsBrowser.objects.create(
            user=user, client="api", show=show, name="", top_group="s"
        )
        # ``filters`` and ``last_route`` are created via separate writes.
        SettingsBrowserFilters.objects.create(browser=browser, favorite=True)
        SettingsBrowserLastRoute.objects.create(
            browser=browser, group="r", pks=[], page=_LAST_ROUTE_PAGE
        )

        browsers = self.store.fetchall("settings_browser")
        match = next(
            r for r in browsers if r["username"] == "alice" and r["client"] == "api"
        )
        assert match["top_group"] == "s"
        assert match["show_p"] == 1
        assert match["show_v"] == 0

        filters = self.store.fetchall("settings_filters")
        match = next(r for r in filters if r["username"] == "alice")
        assert match["favorite"] == 1

        last_route = self.store.fetchall("settings_last_route")
        match = next(r for r in last_route if r["username"] == "alice")
        assert match["group_char"] == "r"
        assert match["page"] == _LAST_ROUTE_PAGE


class UserAuthAgeRatingTests(_SidecarTestCase):
    """UserAuth FK to AgeRatingMetron — surfaced as a string column."""

    def test_user_auth_save_patches_users_row(self) -> None:
        from codex.models.age_rating import AgeRatingMetron

        # AgeRatingMetron is migration-seeded — fetch the existing row.
        rating = AgeRatingMetron.objects.get(name="Mature")
        user = User.objects.create_user(username="alice", password=_TEST_PASSWORD)
        # signal _ensure_user_auth already created the UserAuth row;
        # update it and save to fire the sidecar signal.
        ua = UserAuth.objects.get(user=user)
        ua.age_rating_metron = rating
        ua.save()
        rows = self.store.fetchall("users")
        match = next(r for r in rows if r["username"] == "alice")
        assert match["age_rating_metron_name"] == "Mature"


class BackfillTests(_SidecarTestCase):
    """run_backfill() handles pre-existing main-DB rows."""

    def test_backfill_writes_each_table(self) -> None:
        # Seed the main DB without the sidecar (disconnect signals).
        from codex.user_data import store as store_module

        # Temporarily detach the test store: writes during this block
        # bypass the sidecar so backfill has something to do.
        store_module._store = None  # noqa: SLF001

        user = User.objects.create_user(username="alice", password=_TEST_PASSWORD)
        AdminFlag.objects.update_or_create(key="AU", defaults={"on": True})

        # Reattach so backfill has somewhere to write.
        store_module._store = self.store  # noqa: SLF001
        counts = run_backfill()
        assert counts["users"] >= 1
        assert counts["admin_flags"] >= 1

        assert any(r["username"] == "alice" for r in self.store.fetchall("users"))
        assert any(r["key"] == "AU" for r in self.store.fetchall("admin_flags"))
        del user

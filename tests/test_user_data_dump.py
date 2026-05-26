"""Tests for the on-demand sidecar dump."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import Group, User
from django.test import TestCase

from codex.models.admin import AdminFlag, Timestamp
from codex.user_data.dump import dump_user_data
from codex.user_data.store import SidecarStore, reset_store_for_tests

_TMP_DIR: Final = Path("/tmp/codex.tests.sidecar.dump")  # noqa: S108
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105


class DumpUserDataTests(TestCase):
    """Behavioral tests for ``dump_user_data()``."""

    @override
    def setUp(self) -> None:
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        sidecar_path = _TMP_DIR / "user_data.sqlite"
        for suffix in ("", "-wal", "-shm"):
            sidecar_path.with_name(sidecar_path.name + suffix).unlink(missing_ok=True)
        self.store = SidecarStore(sidecar_path)  # pyright: ignore[reportUninitializedInstanceVariable]
        from codex.user_data import store as store_module

        store_module._store = self.store  # noqa: SLF001

    @override
    def tearDown(self) -> None:
        self.store.close()
        reset_store_for_tests(None)
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_dump_writes_users_and_groups(self) -> None:
        """A dump on a populated main DB writes the expected per-table rows."""
        User.objects.create_user(username="alice", password=_TEST_PASSWORD)
        Group.objects.create(name="editors")

        counts = dump_user_data()
        assert counts["users"] >= 1
        assert counts["groups"] >= 1

        usernames = {r["username"] for r in self.store.fetchall("users")}
        assert "alice" in usernames
        group_names = {r["name"] for r in self.store.fetchall("groups")}
        assert "editors" in group_names

    def test_dump_clears_stale_rows(self) -> None:
        """A second dump removes rows that no longer exist in the main DB."""
        user = User.objects.create_user(username="alice", password=_TEST_PASSWORD)
        dump_user_data()
        usernames = {r["username"] for r in self.store.fetchall("users")}
        assert "alice" in usernames

        user.delete()
        dump_user_data()
        usernames = {r["username"] for r in self.store.fetchall("users")}
        assert "alice" not in usernames

    def test_dump_round_trip_admin_flag(self) -> None:
        """AdminFlag rows round-trip into the sidecar with the right column shape."""
        AdminFlag.objects.update_or_create(
            key="AU", defaults={"on": False, "value": "off"}
        )
        # The API key moved to AdminFlag.AK; codex-version stays on
        # Timestamp.VR. The Timestamp ``version`` column was renamed
        # to ``value`` in migration 0052.
        Timestamp.objects.update_or_create(key="VR", defaults={"value": "1.2.3"})

        dump_user_data()
        flags = {r["key"]: r for r in self.store.fetchall("admin_flags")}
        assert flags["AU"]["on_flag"] == 0
        assert flags["AU"]["value"] == "off"
        timestamps = {r["key"]: r for r in self.store.fetchall("timestamps")}
        assert timestamps["VR"]["value"] == "1.2.3"

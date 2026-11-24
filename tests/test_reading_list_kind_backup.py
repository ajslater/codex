"""A backup keeps the Reading List Kind, and reads a development build's."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from django.contrib.auth.models import User

from codex.models.settings import (
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserShow,
)
from codex.user_data.restore import restore
from tests.test_user_data_restore import _TEST_PASSWORD, _SidecarRestoreCase

if TYPE_CHECKING:
    from pathlib import Path


class ListKindBackupTests(_SidecarRestoreCase):
    """The kind is a list of kinds in the sidecar, like any filter."""

    def _kinds_snapshot(self, kinds: list[str]) -> tuple[User, Path]:
        """Dump a user whose filters pick ``kinds``; drop their settings."""
        user = User.objects.create_user(username="alice", password=_TEST_PASSWORD)
        show, _ = SettingsBrowserShow.objects.get_or_create()
        browser = SettingsBrowser.objects.create(user=user, show=show)
        SettingsBrowserFilters.objects.create(browser=browser, reading_list_kind=kinds)
        snapshot = self._snapshot_sidecar()
        SettingsBrowser.objects.all().delete()
        return user, snapshot

    @staticmethod
    def _restored_kinds(user: User, snapshot: Path) -> list[str]:
        restore(sidecar_path=snapshot)
        return SettingsBrowserFilters.objects.get(browser__user=user).reading_list_kind

    def test_round_trip_restores_list_kinds(self) -> None:
        """The Reading List Kind is a list of kinds, like any filter."""
        user, snapshot = self._kinds_snapshot(["mine", "tags"])
        assert self._restored_kinds(user, snapshot) == ["mine", "tags"]

    def test_a_backup_without_list_kinds_restores(self) -> None:
        """A backup from before the kind restores to every list."""
        user, snapshot = self._kinds_snapshot(["tags"])
        with sqlite3.connect(snapshot) as conn:
            conn.execute("ALTER TABLE settings_filters DROP COLUMN reading_list_kind")
        assert self._restored_kinds(user, snapshot) == []

    def test_a_development_build_kind_restores(self) -> None:
        """A development build wrote one bare kind; unknown kinds drop."""
        user, snapshot = self._kinds_snapshot([])
        for stored, restored in (
            ("mine", ["mine"]),
            ("", []),
            ('"curated"', ["curated"]),
            ('["tags", "everything", "tags"]', ["tags"]),
            ("{}", []),
        ):
            with sqlite3.connect(snapshot) as conn:
                conn.execute(
                    "UPDATE settings_filters SET reading_list_kind = ?", (stored,)
                )
            assert self._restored_kinds(user, snapshot) == restored, stored

"""
Restoring old shelves and the tagging defaults (B27, B28).

Split from ``test_user_data_restore`` with the same sidecar fixture.
"""

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from codex.models import Comic, ReadingList, ReadingListEntry, Series, Volume
from codex.user_data.identifiers import encode_identifier
from codex.user_data.restore import restore
from tests.test_user_data_restore import (
    _INSERT_SHELF_ITEM,
    _OLD_SHELF_TABLES,
    _SEED_SHELF_NAME,
    _TMP_DIR,
    _SidecarRestoreCase,
)


class OldShelfRestoreTests(_SidecarRestoreCase):
    """A backup's shelves restore as lists by the list rules."""

    def test_old_backup_shelf_names_follow_the_list_rules(self) -> None:
        """A shelf whose name cleans to nothing restores as "Reading List"."""
        from codex.models.settings import (
            SettingsBrowser,
            SettingsBrowserFilters,
            SettingsBrowserShow,
        )

        seed = self._seed_main_db()
        show, _ = SettingsBrowserShow.objects.get_or_create()
        browser = SettingsBrowser.objects.create(user=seed["user"], show=show)
        SettingsBrowserFilters.objects.create(browser=browser)
        snapshot = self._snapshot_sidecar()
        blank = "   "
        with sqlite3.connect(snapshot) as conn:
            conn.executescript(_OLD_SHELF_TABLES)
            conn.execute(
                "INSERT INTO shelves (username, name) VALUES ('alice', ?)", (blank,)
            )
            conn.execute(
                _INSERT_SHELF_ITEM.format(shelf="?"),
                (blank, "comics", encode_identifier("comics", [seed["comic_path"]])),
            )
            conn.execute("UPDATE settings_filters SET shelves = ?", (f'["{blank}"]',))
        SettingsBrowser.objects.all().delete()

        restore(sidecar_path=snapshot)

        reading_list = ReadingList.objects.get(user=seed["user"], name="Reading List")
        assert not ReadingList.objects.filter(user=seed["user"], name="").exists()
        assert list(
            ReadingListEntry.objects.filter(reading_list=reading_list).values_list(
                "comic_id", flat=True
            )
        ) == [seed["comic"].pk]
        filters = SettingsBrowserFilters.objects.get(browser__user=seed["user"])
        assert filters.reading_lists == [reading_list.pk]

    def test_old_backup_keeps_a_shelved_comic_not_imported_yet(self) -> None:
        """
        A comic the library does not have yet is a missing issue, found later.

        It was dropped, so a restore run before the import finished lost it
        for good. The rematch after an import finds it by the name in its path.
        """
        from codex.librarian.scribe.readinglists.combine import rematch

        seed = self._seed_main_db()
        snapshot = self._snapshot_sidecar()
        later_path = _TMP_DIR / "comics" / "Civil War 002 (2006).cbz"
        later = str(later_path)
        with sqlite3.connect(snapshot) as conn:
            conn.executescript(_OLD_SHELF_TABLES)
            conn.execute(
                "INSERT INTO shelves (username, name) VALUES ('alice', ?)",
                (_SEED_SHELF_NAME,),
            )
            conn.execute(
                _INSERT_SHELF_ITEM.format(shelf="?"),
                (_SEED_SHELF_NAME, "comics", encode_identifier("comics", [later])),
            )

        restore(sidecar_path=snapshot)

        want = ReadingList.objects.get(user=seed["user"], name=_SEED_SHELF_NAME)
        (entry,) = ReadingListEntry.objects.filter(reading_list=want)
        assert (entry.comic_id, entry.manual) == (None, True)  # pyright: ignore[reportAttributeAccessIssue]
        assert (entry.series_name, entry.issue, entry.year) == ("Civil War", "2", 2006)

        later_path.touch()
        publisher = seed["publisher"]
        series = Series.objects.create(
            name="Civil War", publisher=publisher, imprint=seed["series"].imprint
        )
        volume = Volume.objects.create(
            name="2006", publisher=publisher, imprint=series.imprint, series=series
        )
        comic = Comic.objects.create(
            library=seed["library"],
            path=later,
            issue_number=2,
            year=2006,
            name="Civil War 2",
            publisher=publisher,
            imprint=series.imprint,
            series=series,
            volume=volume,
            size=1,
        )
        assert rematch(want) == 1
        entry.refresh_from_db()
        assert entry.comic_id == comic.pk  # pyright: ignore[reportAttributeAccessIssue]


class TaggingDefaultsRoundTripTests(_SidecarRestoreCase):
    """Every tagging default comes back from a backup."""

    def test_the_run_options_round_trip(self) -> None:
        """Merge all sources, the effort and file renaming are kept."""
        from codex.models.admin import ComicboxTaggingDefaults

        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={
                "merge_all_sources": True,
                "default_effort": "thorough",
                "rename_files": True,
            },
        )
        snapshot = self._snapshot_sidecar()
        ComicboxTaggingDefaults.objects.filter(pk=1).update(
            merge_all_sources=False, default_effort="", rename_files=False
        )

        restore(sidecar_path=snapshot)

        defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        assert (
            defaults.merge_all_sources,
            defaults.default_effort,
            defaults.rename_files,
        ) == (True, "thorough", True)


def _old_dump(snapshot: Path, table: str, dropped: Iterable[str]) -> Path:
    """
    Write a backup as an older release did: a SQL dump lacking some columns.

    A restore replays a dump into a scratch database and adds the columns a
    later release introduced, so only the dump itself says what it carried.
    """
    conn = sqlite3.connect(snapshot)
    try:
        for column in dropped:
            conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        conn.commit()
        dump = snapshot.with_name("old-backup.sql")
        dump.write_text("\n".join(conn.iterdump()), encoding="utf-8")
    finally:
        conn.close()
    return dump


class OldBackupDefaultsTests(_SidecarRestoreCase):
    """A backup older than a setting leaves that setting as it is."""

    def test_old_tagging_defaults_leave_the_newer_ones_alone(self) -> None:
        """Merge all sources, file renaming, the effort and a VerseDB key stay."""
        from codex.models.admin import ComicboxTaggingDefaults

        ComicboxTaggingDefaults.objects.update_or_create(pk=1, defaults={})
        dump = _old_dump(
            self._snapshot_sidecar(),
            "tagging_defaults",
            ("default_effort", "merge_all_sources", "rename_files", "versedb_key"),
        )
        ComicboxTaggingDefaults.objects.filter(pk=1).update(
            merge_all_sources=True,
            rename_files=True,
            default_effort="thorough",
            versedb_key="vdb-token",
        )

        restore(sidecar_path=dump)

        defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        assert (
            defaults.merge_all_sources,
            defaults.rename_files,
            defaults.default_effort,
            defaults.versedb_key,
        ) == (True, True, "thorough", "vdb-token")

    def test_old_settings_defaults_leave_the_newer_ones_alone(self) -> None:
        """A site default the backup did not carry keeps its value."""
        from codex.models.admin import SettingsDefaults

        SettingsDefaults.objects.update_or_create(pk=1, defaults={"cache_book": False})
        dump = _old_dump(self._snapshot_sidecar(), "settings_defaults", ("cache_book",))
        SettingsDefaults.objects.filter(pk=1).update(cache_book=True)

        restore(sidecar_path=dump)

        assert SettingsDefaults.objects.get(pk=1).cache_book

    def test_a_binary_backup_is_left_as_written(self) -> None:
        """Restoring adds no column to the backup, so it says the same next time."""
        from codex.models.admin import ComicboxTaggingDefaults

        ComicboxTaggingDefaults.objects.update_or_create(pk=1, defaults={})
        snapshot = self._snapshot_sidecar()
        conn = sqlite3.connect(snapshot)
        conn.execute("ALTER TABLE tagging_defaults DROP COLUMN rename_files")
        conn.commit()
        conn.close()

        restore(sidecar_path=snapshot)

        conn = sqlite3.connect(snapshot)
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(tagging_defaults)")
        }
        conn.close()
        assert "rename_files" not in columns

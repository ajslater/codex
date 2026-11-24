"""
Restoring old shelves and the tagging defaults (B27, B28).

Split from ``test_user_data_restore`` with the same sidecar fixture.
"""

import sqlite3

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

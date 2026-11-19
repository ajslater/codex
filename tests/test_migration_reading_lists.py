"""
Migration 0061 moves the ``arcs`` collection onto reading lists.

Runs the real migration both ways: back to 0060 to seed story arcs and the
rows that pointed at them, forward to 0061 to check what they became, then
back again to test the reverse data step.
"""

from datetime import date
from typing import Any, Final, override

from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

_BEFORE: Final = [("codex", "0060_post_v2_6_0_schema")]
_AFTER: Final = [("codex", "0061_reading_lists")]
_OLD_FIT: Final = "W"
_NEW_FIT: Final = "H"


def _migrate(target):
    """Migrate to ``target`` and return the app registry at that state."""
    executor = MigrationExecutor(connection)
    executor.migrate(target)
    return MigrationExecutor(connection).loader.project_state(target).apps


class ReadingListsMigrationTests(TransactionTestCase):
    """Arcs become lists in arc order; what named an arc names its list."""

    @override
    def setUp(self) -> None:
        self.addCleanup(_migrate, _AFTER)
        self.user = User.objects.create(username="reader")  # pyright: ignore[reportUninitializedInstanceVariable]

    def _comic(self, apps, hierarchy, name: str, comic_date: date | None):
        library, publisher, imprint, series, volume = hierarchy
        return apps.get_model("codex", "Comic").objects.create(
            library=library,
            path=f"/comics/{name}.cbz",
            name=name,
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            issue_number=int(name[-1]),
            date=comic_date,
            year=comic_date.year if comic_date else None,
            size=1,
        )

    def _hierarchy(self, apps):
        library = apps.get_model("codex", "Library").objects.create(path="/comics")
        publisher = apps.get_model("codex", "Publisher").objects.create(name="P")
        imprint = apps.get_model("codex", "Imprint").objects.create(
            name="I", publisher=publisher
        )
        series = apps.get_model("codex", "Series").objects.create(
            name="S", publisher=publisher, imprint=imprint
        )
        volume = apps.get_model("codex", "Volume").objects.create(
            name=1, publisher=publisher, imprint=imprint, series=series
        )
        return library, publisher, imprint, series, volume

    def _arc(self, apps, name: str):
        return apps.get_model("codex", "StoryArc").objects.create(
            name=name, sort_name=name.lower()
        )

    def _link(self, apps, comic, arc, number):
        san, _ = apps.get_model("codex", "StoryArcNumber").objects.get_or_create(
            story_arc=arc, number=number
        )
        comic.story_arc_numbers.add(san)

    def _seed(self, apps) -> dict:
        hierarchy = self._hierarchy(apps)
        c1 = self._comic(apps, hierarchy, "c1", date(2006, 9, 1))
        c2 = self._comic(apps, hierarchy, "c2", date(2006, 7, 1))
        c3 = self._comic(apps, hierarchy, "c3", None)
        # Two arcs of one sort name are one card today, so one list.
        upper = self._arc(apps, "Civil War")
        lower = self._arc(apps, "civil war")
        other = self._arc(apps, "Other")
        self._link(apps, c1, upper, 2)
        self._link(apps, c1, upper, 7)  # its lowest number orders it
        self._link(apps, c2, lower, 1)
        self._link(apps, c3, upper, None)  # NULL sorts first
        self._link(apps, c1, other, 5)

        shelf = apps.get_model("codex", "Shelf").objects.create(
            user_id=self.user.pk, name="Want"
        )
        item_model = apps.get_model("codex", "ShelfItem")
        item_model.objects.create(shelf=shelf, collection="arcs", target_id=upper.pk)
        item_model.objects.create(shelf=shelf, collection="arcs", target_id=lower.pk)
        item_model.objects.create(shelf=shelf, collection="series", target_id=99)

        reader_model = apps.get_model("codex", "SettingsReader")
        old = reader_model.objects.create(
            user_id=self.user.pk, client="api", story_arc=upper, fit_to=_OLD_FIT
        )
        new = reader_model.objects.create(
            user_id=self.user.pk, client="api", story_arc=lower, fit_to=_NEW_FIT
        )
        reader_model.objects.filter(pk=old.pk).update(updated_at=date(2020, 1, 1))
        reader_model.objects.filter(pk=new.pk).update(updated_at=date(2021, 1, 1))

        show, _ = apps.get_model("codex", "SettingsBrowserShow").objects.get_or_create()
        browser = apps.get_model("codex", "SettingsBrowser").objects.create(
            user_id=self.user.pk, show=show
        )
        apps.get_model("codex", "SettingsBrowserLastRoute").objects.create(
            browser=browser, collection="arcs", pks=[lower.pk, upper.pk, 9999]
        )
        # A saved view filtering on a story arc, sorting by Story Arcs, with
        # the Story Arcs column showing.
        apps.get_model("codex", "SettingsBrowserFilters").objects.create(
            browser=browser, story_arcs=[upper.pk, None]
        )
        browser.order_by = "story_arcs"
        browser.order_extra_keys = [{"key": "story_arcs", "reverse": False}]
        browser.collection_order_memory = {"s": {"order_by": "story_arcs"}}
        browser.table_columns = {"series": ["name", "story_arcs"]}
        browser.save()
        return {"comics": (c1, c2, c3), "upper": upper, "browser": browser}

    def test_arcs_become_reading_lists(self) -> None:
        """Forward: one list per sort name, in arc order; pointers remapped."""
        seeded = self._seed(_migrate(_BEFORE))
        c1, c2, c3 = seeded["comics"]
        apps = _migrate(_AFTER)

        reading_list_model = apps.get_model("codex", "ReadingList")
        assert sorted(reading_list_model.objects.values_list("name", flat=True)) == [
            "Civil War",
            "Other",
        ]
        civil_war: Any = reading_list_model.objects.get(sort_name="civil war")
        assert civil_war.user_id is None
        entries = civil_war.entries.order_by("position")
        assert list(entries.values_list("position", "comic_id", "match_tier")) == [
            (0, c3.pk, "tagged"),
            (1, c2.pk, "tagged"),
            (2, c1.pk, "tagged"),
        ]
        source = civil_war.sources.get()
        assert (source.kind, source.ref, source.revision) == ("tags", "civil war", "")
        assert source.ordered is False  # c3 has no number

        items = apps.get_model("codex", "ShelfItem").objects.order_by("collection")
        assert list(items.values_list("collection", "target_id")) == [
            ("arcs", civil_war.pk),
            ("series", 99),
        ]

        reader: Any = apps.get_model("codex", "SettingsReader").objects.get(
            user_id=self.user.pk
        )
        assert (reader.reading_list_id, reader.fit_to) == (civil_war.pk, _NEW_FIT)

        route: Any = apps.get_model("codex", "SettingsBrowserLastRoute").objects.get(
            browser_id=seeded["browser"].pk
        )
        assert route.pks == [civil_war.pk]

    def test_story_arc_settings_become_reading_lists(self) -> None:
        """A story-arc filter, sort and column come out as reading-list ones."""
        seeded = self._seed(_migrate(_BEFORE))
        apps = _migrate(_AFTER)
        civil_war: Any = apps.get_model("codex", "ReadingList").objects.get(
            sort_name="civil war"
        )
        filters: Any = apps.get_model("codex", "SettingsBrowserFilters").objects.get(
            browser_id=seeded["browser"].pk
        )
        assert filters.reading_lists == [civil_war.pk, None]
        assert not hasattr(filters, "story_arcs")
        browser: Any = apps.get_model("codex", "SettingsBrowser").objects.get(
            pk=seeded["browser"].pk
        )
        assert browser.order_by == "reading_lists"
        assert browser.order_extra_keys == [{"key": "reading_lists", "reverse": False}]
        assert browser.collection_order_memory == {"s": {"order_by": "reading_lists"}}
        assert browser.table_columns == {"series": ["name", "reading_lists"]}

    def test_reverse_gives_story_arc_settings_back(self) -> None:
        """Backward: the filter, sort and column name story arcs again."""
        seeded = self._seed(_migrate(_BEFORE))
        _migrate(_AFTER)
        apps = _migrate(_BEFORE)
        filters: Any = apps.get_model("codex", "SettingsBrowserFilters").objects.get(
            browser_id=seeded["browser"].pk
        )
        assert filters.story_arcs == [seeded["upper"].pk, None]
        browser: Any = apps.get_model("codex", "SettingsBrowser").objects.get(
            pk=seeded["browser"].pk
        )
        assert browser.order_by == "story_arcs"
        assert browser.table_columns == {"series": ["name", "story_arcs"]}

    def test_reverse_points_back_at_arcs(self) -> None:
        """Backward: lists from tags give their pointers back to an arc."""
        seeded = self._seed(_migrate(_BEFORE))
        _migrate(_AFTER)
        apps = _migrate(_BEFORE)
        upper = seeded["upper"]

        item: Any = apps.get_model("codex", "ShelfItem").objects.get(collection="arcs")
        assert item.target_id == upper.pk
        reader: Any = apps.get_model("codex", "SettingsReader").objects.get(
            user_id=self.user.pk
        )
        assert reader.story_arc_id == upper.pk
        route: Any = apps.get_model("codex", "SettingsBrowserLastRoute").objects.get(
            browser_id=seeded["browser"].pk
        )
        assert route.pks == [upper.pk]

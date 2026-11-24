"""
Migration 0061 folds shelves into reading lists.

Seeds shelves at 0060 and migrates forward: each shelf becomes a personal
list of its name, its comics entries added by hand, and every other item a
collection item whose comics are written in the same step. The live sync
must find nothing to change in what the migration wrote. Then back to
0060 and forward again.
"""

from datetime import date
from typing import Any, Final, override

from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from codex.librarian.scribe.readinglists.live import (
    item_identity,
    load_target,
    reconcile_list,
)
from codex.models import ReadingList, ReadingListSource

_BEFORE: Final = [("codex", "0060_post_v2_6_0_schema")]
_AFTER: Final = [("codex", "0061_reading_lists_and_versedb_key")]
_GONE: Final = 9999


def _migrate(target):
    """Migrate to ``target`` and return the app registry at that state."""
    executor = MigrationExecutor(connection)
    executor.migrate(target)
    return MigrationExecutor(connection).loader.project_state(target).apps


def _objects(apps, name: str) -> Any:
    return apps.get_model("codex", name).objects


class _Library:
    """
    Marvel: Daredevil (1964) with d1 and d2 in folder dd, X-Men with x1.

    Two story arcs share the sort name "civil war": d1 is in one, x1 in
    the other, so the arcs step makes one global list of [d1, x1].
    """

    def __init__(self, apps) -> None:
        self.apps = apps
        self.library = _objects(apps, "Library").create(path="/comics")
        self.publisher = _objects(apps, "Publisher").create(name="Marvel")
        self.imprint = _objects(apps, "Imprint").create(
            name="Marvel", publisher=self.publisher
        )
        self.daredevil = self._series("Daredevil")
        self.xmen = self._series("X-Men")
        self.volume = self._volume(self.daredevil, 1964)
        self.folder = _objects(apps, "Folder").create(
            library=self.library, path="/comics/dd", name="dd", sort_name="dd"
        )
        self.d1 = self._comic("d1", self.volume, 1, folder=self.folder)
        self.d2 = self._comic("d2", self.volume, 2, folder=self.folder)
        self.x1 = self._comic("x1", self._volume(self.xmen, 1), 1)
        self.upper = self._arc("Civil War", self.d1, 1)
        self.lower = self._arc("civil war", self.x1, 2)

    def _series(self, name: str):
        return _objects(self.apps, "Series").create(
            name=name,
            sort_name=name.lower(),
            publisher=self.publisher,
            imprint=self.imprint,
        )

    def _volume(self, series, name: int):
        return _objects(self.apps, "Volume").create(
            name=name, publisher=self.publisher, imprint=self.imprint, series=series
        )

    def _comic(self, name: str, volume, number: int, folder=None):
        comic = _objects(self.apps, "Comic").create(
            library=self.library,
            path=f"/comics/dd/{name}.cbz" if folder else f"/comics/{name}.cbz",
            parent_folder=folder,
            name=name,
            publisher=self.publisher,
            imprint=self.imprint,
            series=volume.series,
            volume=volume,
            issue_number=number,
            date=date(2006, number, 1),
            year=2006,
            size=1,
        )
        if folder:
            comic.folders.add(folder)
        return comic

    def _arc(self, name: str, comic, number: int):
        arc = _objects(self.apps, "StoryArc").create(name=name, sort_name=name.lower())
        san = _objects(self.apps, "StoryArcNumber").create(story_arc=arc, number=number)
        comic.story_arc_numbers.add(san)
        return arc

    def shelf(self, user, name: str, items=()):
        """Shelve ``items``, ``(collection, target pk)``, in order."""
        shelf = _objects(self.apps, "Shelf").create(user_id=user.pk, name=name)
        for collection, target_id in items:
            _objects(self.apps, "ShelfItem").create(
                shelf=shelf, collection=collection, target_id=target_id
            )
        return shelf

    def every_kind(self) -> tuple:
        """Return a comic, then one of every collection, then both Civil War arcs."""
        return (
            ("comics", self.x1.pk),
            ("publishers", self.publisher.pk),
            ("imprints", self.imprint.pk),
            ("series", self.daredevil.pk),
            ("volumes", self.volume.pk),
            ("folders", self.folder.pk),
            ("arcs", self.upper.pk),
            ("arcs", self.lower.pk),
        )


def _personal(apps, user, name: str) -> Any:
    return _objects(apps, "ReadingList").get(user_id=user.pk, name=name)


def _entries(reading_list) -> list[tuple]:
    """Each entry's comic, and the collection that delivered it, in order."""
    return [
        (entry.comic_id, entry.live_source.collection if entry.live_source_id else None)
        for entry in reading_list.entries.order_by("position").select_related(
            "live_source"
        )
    ]


def _items(reading_list) -> list[tuple]:
    return list(
        reading_list.sources.order_by("rank").values_list(
            "kind", "collection", "target_id", "position", "revision"
        )
    )


def _assert_in_sync(reading_list) -> None:
    """Check the live sync agrees with every row the migration wrote."""
    real = ReadingList.objects.get(pk=reading_list.pk)
    for item in ReadingListSource.objects.filter(reading_list=real):
        target = load_target(item.collection, item.target_id)
        assert target is not None, item.collection
        assert item_identity(item.collection, target) == (item.ref, item.document)
    assert not reconcile_list(real)


class _Fixture(TransactionTestCase):
    """Two users; the schema back at 0061 after each test."""

    @override
    def setUp(self) -> None:
        self.addCleanup(_migrate, _AFTER)
        self.reader = User.objects.create(username="reader")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.other = User.objects.create(username="other")  # pyright: ignore[reportUninitializedInstanceVariable]

    def browser(self, apps, name: str = "", client: str = "api"):
        """Make one of the reader's browser settings rows."""
        show, _ = _objects(apps, "SettingsBrowserShow").get_or_create()
        return _objects(apps, "SettingsBrowser").create(
            user_id=self.reader.pk, show=show, name=name, client=client
        )


class ShelvesToListsTests(_Fixture):
    """Each shelf comes out a personal list holding what it held."""

    def test_a_shelf_with_every_kind(self) -> None:
        """Its comic by hand; each collection an item; one list for two arcs."""
        seed = _Library(_migrate(_BEFORE))
        seed.shelf(self.reader, "Every", seed.every_kind())
        apps = _migrate(_AFTER)

        every = _personal(apps, self.reader, "Every")
        civil_war = _objects(apps, "ReadingList").get(user__isnull=True)
        # Every item sits after the one comic shelved before it; the
        # revision is blank so the first sync verifies it.
        assert _items(every) == [
            ("collection", "publishers", seed.publisher.pk, 1, ""),
            ("collection", "imprints", seed.imprint.pk, 1, ""),
            ("collection", "series", seed.daredevil.pk, 1, ""),
            ("collection", "volumes", seed.volume.pk, 1, ""),
            ("collection", "folders", seed.folder.pk, 1, ""),
            ("collection", "arcs", civil_war.pk, 1, ""),
        ]
        labels = [item.document["label"] for item in every.sources.order_by("rank")]
        assert labels == [
            "Marvel",
            "Marvel",
            "Daredevil",
            "Daredevil (1964)",
            "dd",
            "Civil War",
        ]
        # The publisher delivers every comic not already on the list.
        assert _entries(every) == [
            (seed.x1.pk, None),
            (seed.d1.pk, "publishers"),
            (seed.d2.pk, "publishers"),
        ]
        hand: Any = every.entries.get(comic_id=seed.x1.pk)
        assert (hand.match_tier, hand.manual, hand.series_name, hand.issue) == (
            "manual",
            True,
            "X-Men",
            "1",
        )
        assert hand.reference["series"] == {"name": "X-Men"}
        _assert_in_sync(every)

    def test_a_comic_shelved_directly_and_through_its_series(self) -> None:
        """It appears once, as the entry added by hand."""
        seed = _Library(_migrate(_BEFORE))
        seed.shelf(
            self.reader,
            "Once",
            (("series", seed.daredevil.pk), ("comics", seed.d1.pk)),
        )
        apps = _migrate(_AFTER)

        once = _personal(apps, self.reader, "Once")
        assert _entries(once) == [(seed.d2.pk, "series"), (seed.d1.pk, None)]
        _assert_in_sync(once)

    def test_names(self) -> None:
        """Cleaned as list names are, never empty, unique per user."""
        seed = _Library(_migrate(_BEFORE))
        for name in ("Want", "Want ", "<script>x</script>", "   ", "The Pile"):
            seed.shelf(self.reader, name)
        seed.shelf(self.other, "Want")
        seed.shelf(self.reader, "Empty")
        apps = _migrate(_AFTER)

        lists = _objects(apps, "ReadingList").filter(user__isnull=False)
        mine = lists.filter(user_id=self.reader.pk).order_by("pk")
        assert list(mine.values_list("name", flat=True)) == [
            "Want",
            "Want (2)",
            "Reading List",
            "Reading List (2)",
            "The Pile",
            "Empty",
        ]
        assert mine.get(name="The Pile").sort_name == "pile, the"
        assert list(
            lists.filter(user_id=self.other.pk).values_list("name", flat=True)
        ) == ["Want"]
        empty = _personal(apps, self.reader, "Empty")
        assert (empty.entries.count(), empty.sources.count()) == (0, 0)

    def test_orphans_are_dropped(self) -> None:
        """
        No list for a gone user; no rows for gone comics or collections.

        SQLite checks foreign keys only when asked, so a shelf can outlive
        its user; ``migrate`` ends by asking.
        """
        seed = _Library(_migrate(_BEFORE))
        ghost = User.objects.create(username="ghost")
        ghost_pk = ghost.pk
        seed.shelf(ghost, "Haunted", (("comics", seed.d1.pk),))
        seed.shelf(
            self.reader,
            "Gone",
            (
                ("comics", _GONE),
                ("series", _GONE),
                ("folders", _GONE),
                ("arcs", _GONE),
            ),
        )
        connection.disable_constraint_checking()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM codex_userauth WHERE user_id = %s", [ghost_pk]
                )
                cursor.execute("DELETE FROM auth_user WHERE id = %s", [ghost_pk])
        finally:
            connection.enable_constraint_checking()
        apps = _migrate(_AFTER)

        lists = _objects(apps, "ReadingList")
        assert not lists.filter(user_id=ghost_pk).exists()
        gone = _personal(apps, self.reader, "Gone")
        assert (gone.entries.count(), gone.sources.count()) == (0, 0)
        connection.check_constraints()

    def test_filters(self) -> None:
        """A shelves filter becomes a Reading Lists filter on its list."""
        apps = _migrate(_BEFORE)
        seed = _Library(apps)
        want = seed.shelf(self.reader, "Want", (("comics", seed.d1.pk),))
        filters = _objects(apps, "SettingsBrowserFilters")
        live = self.browser(apps)
        saved = self.browser(apps, name="saved")
        opds = self.browser(apps, client="opds")
        filters.create(browser=live, shelves=[want.pk])
        filters.create(
            browser=saved, shelves=[want.pk, _GONE], story_arcs=[seed.upper.pk, None]
        )
        filters.create(browser=opds, shelves=[_GONE])
        apps = _migrate(_AFTER)

        mine = _personal(apps, self.reader, "Want")
        civil_war = _objects(apps, "ReadingList").get(user__isnull=True)
        rows = _objects(apps, "SettingsBrowserFilters")
        assert rows.get(browser_id=live.pk).reading_lists == [mine.pk]
        # The "in no list" choice the story-arc filter kept stays last.
        assert rows.get(browser_id=saved.pk).reading_lists == [
            civil_war.pk,
            mine.pk,
            None,
        ]
        assert rows.get(browser_id=opds.pk).reading_lists == []

    def test_sort_and_column_keys(self) -> None:
        """``shelved`` becomes ``reading_lists`` wherever a key is stored."""
        apps = _migrate(_BEFORE)
        live = self.browser(apps)
        live.order_by = "shelved"
        live.order_extra_keys = [{"key": "shelved", "reverse": True}]
        live.collection_order_memory = {
            "s": {
                "order_by": "shelved",
                "order_extra_keys": [{"key": "shelved", "reverse": False}],
            }
        }
        live.table_columns = {"series": ["name", "shelved"]}
        live.save()
        # Both old keys on one view: one column, one sort, the first wins.
        both = self.browser(apps, name="both")
        both.order_extra_keys = [
            {"key": "story_arcs", "reverse": False},
            {"key": "shelved", "reverse": True},
        ]
        both.table_columns = {"series": ["story_arcs", "name", "shelved"]}
        both.save()
        _objects(apps, "SettingsDefaults").create(
            order_by="shelved", table_columns={"series": ["shelved"]}
        )
        apps = _migrate(_AFTER)

        browsers = _objects(apps, "SettingsBrowser")
        live = browsers.get(pk=live.pk)
        assert live.order_by == "reading_lists"
        assert live.order_extra_keys == [{"key": "reading_lists", "reverse": True}]
        assert live.collection_order_memory == {
            "s": {
                "order_by": "reading_lists",
                "order_extra_keys": [{"key": "reading_lists", "reverse": False}],
            }
        }
        assert live.table_columns == {"series": ["name", "reading_lists"]}
        both = browsers.get(pk=both.pk)
        assert both.order_extra_keys == [{"key": "reading_lists", "reverse": False}]
        assert both.table_columns == {"series": ["reading_lists", "name"]}
        defaults = _objects(apps, "SettingsDefaults").get()
        assert defaults.order_by == "reading_lists"
        assert defaults.table_columns == {"series": ["reading_lists"]}


def _snapshot(apps) -> dict:
    """
    Return what a round trip keeps: per list its items, comics, filters.

    Order is not kept: a shelf had none of its own. Lists from tags are
    rebuilt with new pks, so items and filters are compared by name.
    """
    lists = _objects(apps, "ReadingList")
    names = dict(lists.values_list("pk", "name"))
    personal = {}
    for reading_list in lists.filter(user__isnull=False):
        items = {
            (item.collection, item.document["label"])
            for item in reading_list.sources.all()
        }
        personal[reading_list.user_id, reading_list.name] = (
            items,
            sorted(_entries(reading_list), key=str),
        )
    filters = {
        row.browser_id: [names.get(pk) for pk in row.reading_lists]
        for row in _objects(apps, "SettingsBrowserFilters").all()
    }
    return {"lists": personal, "filters": filters}


class RoundTripTests(_Fixture):
    """Back to 0060 rebuilds shelves; forward again makes the same lists."""

    def test_reverse_and_forward_again(self) -> None:
        """Shelves come back holding what the lists held, then lists again."""
        apps = _migrate(_BEFORE)
        seed = _Library(apps)
        seed.shelf(self.reader, "Every", seed.every_kind())
        seed.shelf(
            self.reader,
            "Once",
            (("series", seed.daredevil.pk), ("comics", seed.d1.pk)),
        )
        want = seed.shelf(self.reader, "Want ")
        seed.shelf(self.reader, "Want")
        seed.shelf(self.other, "Empty")
        browser = self.browser(apps)
        _objects(apps, "SettingsBrowserFilters").create(
            browser=browser, shelves=[want.pk], story_arcs=[seed.upper.pk, None]
        )
        first = _snapshot(_migrate(_AFTER))

        apps = _migrate(_BEFORE)
        shelves = _objects(apps, "Shelf")
        assert set(shelves.values_list("user_id", "name")) == {
            (self.reader.pk, "Every"),
            (self.reader.pk, "Once"),
            (self.reader.pk, "Want"),
            (self.reader.pk, "Want (2)"),
            (self.other.pk, "Empty"),
        }
        every = shelves.get(name="Every")
        # The two arcs went to one list and come back as its first arc.
        assert set(every.items.values_list("collection", "target_id")) == set(
            seed.every_kind()[:-1]
        )
        row = _objects(apps, "SettingsBrowserFilters").get(browser_id=browser.pk)
        assert row.shelves == [shelves.get(name="Want").pk]
        assert row.story_arcs == [seed.upper.pk, None]

        assert _snapshot(_migrate(_AFTER)) == first

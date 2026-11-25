"""
Collection items: a whole series, folder or list in a reading list, kept current.

An item's comics are stored as live entries that :func:`reconcile_list`
alone writes. These tests hold each item kind, the once-per-list rule,
growth and shrink, dangling and re-binding, list-in-list order and guards,
the import-time sync and the sweep.
"""

import json
from datetime import date
from multiprocessing import Event, Lock
from typing import Any, Final, override
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from loguru import logger

from codex.librarian.scribe.importer.init import Counts
from codex.librarian.scribe.importer.readinglists import ReadingListsImporter
from codex.librarian.scribe.janitor.janitor import _NIGHTLY_TASKS, Janitor
from codex.librarian.scribe.janitor.tasks import JanitorRematchReadingListsTask
from codex.librarian.scribe.priority import get_task_priority
from codex.librarian.scribe.readinglists import live
from codex.librarian.scribe.readinglists.live import (
    ItemRefusedError,
    add_item,
    reconcile_includers,
    reconcile_list,
    sweep_live,
    sync_live,
)
from codex.librarian.scribe.readinglists.service import import_document
from codex.librarian.scribe.readinglists.tasks import ReadingListLiveSyncTask
from codex.models import (
    Comic,
    Folder,
    ReadingList,
    ReadingListEntry,
    ReadingListSource,
    Series,
    Volume,
)
from codex.models.readinglist import ReadingListMatchTier
from tests.test_reading_list_combine import _document, _upload
from tests.test_reading_list_fetch import _Queue
from tests.test_reading_lists import TMP_DIR, ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_IMPORTER_SYNC_LIVE: Final = "codex.librarian.scribe.importer.readinglists.sync_live"
_REAPER_SWEEP: Final = "codex.librarian.scribe.janitor.reap.sweep_live"


class LiveFixture(ReadingListFixture):
    """Four Civil War comics, their folder links, and a reader's own list."""

    @override
    def setUp(self) -> None:
        super().setUp()
        first = self.comics[0]
        self.publisher = first.publisher  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = first.imprint  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series = first.series  # pyright: ignore[reportUninitializedInstanceVariable]
        self.volume = first.volume  # pyright: ignore[reportUninitializedInstanceVariable]
        assert first.parent_folder is not None
        self.folder: Folder = first.parent_folder  # pyright: ignore[reportUninitializedInstanceVariable]
        for comic in self.comics:
            comic.folders.add(self.folder)
        self.reader = User.objects.create_user(username="reader", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.mine = ReadingList.objects.create(name="Mine", user=self.reader)  # pyright: ignore[reportUninitializedInstanceVariable]

    def make_comic(
        self, series: Series, volume: Volume, number: int, folder: Folder | None = None
    ) -> Comic:
        """Make a comic the way the fixture does, in its own folder."""
        folder = folder or self.folder
        path = TMP_DIR / f"{series.name}-{number}.cbz"
        path.touch()
        comic = Comic.objects.create(
            library=self.library,
            path=path,
            name=f"{series.name} {number}",
            issue_number=number,
            year=2006,
            date=date(2006, 1, 1),
            publisher=series.publisher,
            imprint=series.imprint,
            series=series,
            volume=volume,
            parent_folder=folder,
            size=1,
            page_count=10,
        )
        comic.folders.add(*Folder.objects.filter(pk=folder.pk))
        return comic

    def make_series(self, name: str, count: int = 2) -> tuple[Series, list[Comic]]:
        """Another series of the same imprint, with ``count`` issues."""
        series = Series.objects.create(
            name=name, imprint=self.imprint, publisher=self.publisher
        )
        volume = Volume.objects.create(
            name=2011, series=series, imprint=self.imprint, publisher=self.publisher
        )
        return series, [
            self.make_comic(series, volume, number) for number in range(1, count + 1)
        ]

    @staticmethod
    def hold(
        reading_list: ReadingList, collection: str, target: Any, position=None
    ) -> ReadingListSource:
        """Add a collection item and sync the list."""
        item = add_item(reading_list, collection, target.pk, position=position)
        reconcile_list(reading_list)
        return item

    def pks(self, comics) -> list[int]:
        """Comic pks, for comparing against :meth:`order`."""
        del self
        return [comic.pk for comic in comics]


class ItemKindTests(LiveFixture):
    """Every collection delivers its comics, in reading order."""

    def test_each_kind_delivers_its_comics(self) -> None:
        """Publisher, imprint, series, volume and folder hold the four issues."""
        targets = {
            "publishers": self.publisher,
            "imprints": self.imprint,
            "series": self.series,
            "volumes": self.volume,
            "folders": self.folder,
        }
        for collection, target in targets.items():
            reading_list = ReadingList.objects.create(name=collection, user=self.reader)
            self.hold(reading_list, collection, target)
            assert self.order(reading_list) == self.pks(self.comics), collection
            assert not ReadingListEntry.objects.filter(
                reading_list=reading_list, live_source__isnull=True
            ).exists()

    def test_live_entries_are_marked(self) -> None:
        """A delivered comic's entry names its item and its tier."""
        item = self.hold(self.mine, "series", self.series)
        entry = ReadingListEntry.objects.filter(reading_list=self.mine).first()
        assert entry is not None
        assert entry.live_source_id == item.pk  # pyright: ignore[reportAttributeAccessIssue]
        assert entry.match_tier == ReadingListMatchTier.COLLECTION
        assert not entry.manual

    def test_a_folder_holds_its_subfolders_comics(self) -> None:
        """Comics link every ancestor folder, so the root folder holds them."""
        (TMP_DIR / "child").mkdir(parents=True, exist_ok=True)
        child = Folder.objects.create(
            library=self.library,
            path=str(TMP_DIR / "child"),
            name="child",
            parent_folder=self.folder,
        )
        nested = self.make_comic(self.series, self.volume, 5, folder=child)
        nested.folders.add(self.folder)
        self.hold(self.mine, "folders", self.folder)
        assert nested.pk in self.order(self.mine)

    def test_a_list_holds_another_list_in_its_order(self) -> None:
        """A list item delivers the other list's comics in that list's order."""
        c1, _, c3, _ = self.comics
        inner = ReadingList.objects.create(name="Inner", user=self.reader)
        ReadingListEntry.objects.create(reading_list=inner, comic=c3, manual=True)
        ReadingListEntry.objects.create(
            reading_list=inner, comic=c1, manual=True, position=1
        )
        self.hold(self.mine, "arcs", inner)
        assert self.order(self.mine) == [c3.pk, c1.pk]

    def test_a_comic_pending_delete_keeps_its_row(self) -> None:
        """A comic whose file went missing is still the series' issue."""
        c1 = self.comics[0]
        Comic.objects.filter(pk=c1.pk).update(missing_since=timezone.now())
        self.hold(self.mine, "series", self.series)
        assert c1.pk in self.order(self.mine)


class OncePerListTests(LiveFixture):
    """A comic appears in a list once, however many items hold it."""

    def test_a_hand_added_comic_is_not_delivered_again(self) -> None:
        """The series skips the issue the list already holds by hand."""
        c1, c2, c3, c4 = self.comics
        ReadingListEntry.objects.create(reading_list=self.mine, comic=c2, manual=True)
        self.hold(self.mine, "series", self.series)
        assert self.order(self.mine) == [c2.pk, c1.pk, c3.pk, c4.pk]

    def test_overlapping_items_share_their_comics(self) -> None:
        """The publisher delivers only what the series did not."""
        dashdemon, more = self.make_series("Dashdemon")
        self.hold(self.mine, "series", self.series)
        self.hold(self.mine, "publishers", self.publisher)
        order = self.order(self.mine)
        assert len(order) == len(set(order))
        assert set(order) == {*self.pks(self.comics), *self.pks(more)}
        assert order[:4] == self.pks(self.comics)
        del dashdemon

    def test_a_hidden_entry_keeps_its_comic_out(self) -> None:
        """A comic a person hid is not brought back by a series."""
        c1 = self.comics[0]
        ReadingListEntry.objects.create(
            reading_list=self.mine, comic=c1, manual=True, ignored=True
        )
        self.hold(self.mine, "series", self.series)
        live_comics = ReadingListEntry.objects.filter(
            reading_list=self.mine, live_source__isnull=False
        ).values_list("comic_id", flat=True)
        assert c1.pk not in set(live_comics)


class GrowthTests(LiveFixture):
    """An item follows its collection."""

    def test_a_new_issue_joins_and_a_deleted_one_leaves(self) -> None:
        """The series grows and shrinks, in order."""
        self.hold(self.mine, "series", self.series)
        c5 = self.make_comic(self.series, self.volume, 5)
        assert reconcile_list(self.mine)
        assert self.order(self.mine) == [*self.pks(self.comics), c5.pk]
        self.comics[0].delete()
        assert reconcile_list(self.mine)
        assert self.order(self.mine) == [*self.pks(self.comics[1:]), c5.pk]

    def test_nothing_changes_twice(self) -> None:
        """A second reconcile with nothing new writes nothing."""
        self.hold(self.mine, "series", self.series)
        assert not reconcile_list(self.mine)

    def test_positions_stay_dense(self) -> None:
        """Every entry is numbered 0..n-1 in order."""
        c1 = self.comics[0]
        ReadingListEntry.objects.create(reading_list=self.mine, comic=c1, manual=True)
        self.hold(self.mine, "series", self.series)
        positions = list(
            ReadingListEntry.objects.filter(reading_list=self.mine)
            .order_by("position", "pk")
            .values_list("position", flat=True)
        )
        assert positions == list(range(len(positions)))


class DanglingTests(LiveFixture):
    """An item outlives its target and finds it again."""

    def test_a_gone_series_dangles_and_comes_back(self) -> None:
        """Deleting the series keeps the item; a new series of its name binds."""
        dashdemon, _ = self.make_series("Dashdemon")
        item = self.hold(self.mine, "series", dashdemon)
        dashdemon.delete()
        reconcile_list(self.mine)
        item.refresh_from_db()
        assert item.target_id is None
        assert self.order(self.mine) == []
        again, comics = self.make_series("Dashdemon")
        reconcile_list(self.mine)
        item.refresh_from_db()
        assert item.target_id == again.pk
        assert self.order(self.mine) == self.pks(comics)

    def test_a_moved_folder_keeps_its_item_current(self) -> None:
        """A folder moved in place keeps its pk; the item's identity follows."""
        item = self.hold(self.mine, "folders", self.folder)
        moved = str(TMP_DIR / "moved")
        Folder.objects.filter(pk=self.folder.pk).update(path=moved)
        reconcile_list(self.mine)
        item.refresh_from_db()
        assert moved in item.ref
        assert item.target_id == self.folder.pk


class GuardTests(LiveFixture):
    """Some items are refused outright."""

    def test_a_list_cannot_hold_itself(self) -> None:
        """Self-inclusion is a cycle of one."""
        with pytest.raises(ItemRefusedError):
            add_item(self.mine, "arcs", self.mine.pk)

    def test_a_cycle_is_refused(self) -> None:
        """A holds B, so B may not hold A."""
        inner = ReadingList.objects.create(name="Inner", user=self.reader)
        add_item(self.mine, "arcs", inner.pk)
        with pytest.raises(ItemRefusedError):
            add_item(inner, "arcs", self.mine.pk)

    def test_a_global_list_cannot_hold_a_personal_one(self) -> None:
        """Everyone would see one person's list through it."""
        shared = ReadingList.objects.create(name="Shared")
        with pytest.raises(ItemRefusedError):
            add_item(shared, "arcs", self.mine.pk)

    def test_someone_elses_list_is_refused(self) -> None:
        """A personal list holds only global lists and its owner's own."""
        other = User.objects.create_user(username="other", password=_PW)
        theirs = ReadingList.objects.create(name="Theirs", user=other)
        with pytest.raises(ItemRefusedError):
            add_item(self.mine, "arcs", theirs.pk)

    def test_an_item_is_held_once(self) -> None:
        """Adding the same series again is refused."""
        add_item(self.mine, "series", self.series.pk)
        with pytest.raises(ItemRefusedError):
            add_item(self.mine, "series", self.series.pk)


class ListInListTests(LiveFixture):
    """Lists that hold lists follow them, targets first."""

    def _nested(self) -> tuple[ReadingList, ReadingList]:
        inner = ReadingList.objects.create(name="Inner", user=self.reader)
        self.hold(inner, "series", self.series)
        self.hold(self.mine, "arcs", inner)
        return inner, self.mine

    def test_sync_does_targets_first(self) -> None:
        """One forced sync carries a new issue through both lists."""
        inner, outer = self._nested()
        c5 = self.make_comic(self.series, self.volume, 5)
        sync_live(force=True)
        assert c5.pk in self.order(inner)
        assert c5.pk in self.order(outer)

    def test_includers_follow_a_changed_list(self) -> None:
        """A hand edit to the inner list reaches the outer one."""
        inner, outer = self._nested()
        _, more = self.make_series("Dashdemon", count=1)
        ReadingListEntry.objects.create(
            reading_list=inner, comic=more[0], manual=True, position=99
        )
        reconcile_list(inner)
        reconcile_includers(inner)
        assert more[0].pk in self.order(outer)

    def test_a_deleted_inner_list_queues_its_includers(self) -> None:
        """Deleting a list asks the librarian to sync the lists holding it."""
        inner, outer = self._nested()
        with patch("codex.signals.django_signals.LIBRARIAN_QUEUE") as queue:
            inner.delete()
        task = queue.put.call_args.args[0]
        assert task.list_pks == (outer.pk,)


class SyncTests(LiveFixture):
    """The import-time sync reconciles only lists whose items changed."""

    def test_unchanged_lists_are_skipped(self) -> None:
        """Digests match: nothing to do until a series changes."""
        self.hold(self.mine, "series", self.series)
        with patch.object(live, "reconcile_list", wraps=live.reconcile_list) as spy:
            sync_live()
            assert spy.call_count == 0
            self.make_comic(self.series, self.volume, 5)
            sync_live()
            assert spy.call_count == 1
            sync_live(force=True)
            assert spy.call_count == 2  # noqa: PLR2004

    def test_the_sweep_drops_rows_whose_comic_is_gone(self) -> None:
        """A deleted comic leaves its live row comicless until the sweep."""
        self.hold(self.mine, "series", self.series)
        self.comics[0].delete()
        assert sweep_live() == 1
        assert not ReadingListEntry.objects.filter(
            reading_list=self.mine, comic__isnull=True
        ).exists()


class PlacementTests(LiveFixture):
    """Where a block sits among the list's other entries."""

    def test_a_block_sits_where_it_was_put_in_a_hand_made_list(self) -> None:
        """Between two hand-added issues, and it stays there."""
        dashdemon, more = self.make_series("Dashdemon")
        c1, c2, _, _ = self.comics
        ReadingListEntry.objects.create(reading_list=self.mine, comic=c1, manual=True)
        ReadingListEntry.objects.create(
            reading_list=self.mine, comic=c2, manual=True, position=1
        )
        self.hold(self.mine, "series", dashdemon, position=1)
        expected = [c1.pk, *self.pks(more), c2.pk]
        assert self.order(self.mine) == expected
        reconcile_list(self.mine)
        assert self.order(self.mine) == expected

    def test_an_emptied_block_keeps_its_place(self) -> None:
        """A series that empties and refills comes back where it was."""
        dashdemon, more = self.make_series("Dashdemon", count=1)
        c1, c2, _, _ = self.comics
        ReadingListEntry.objects.create(reading_list=self.mine, comic=c1, manual=True)
        ReadingListEntry.objects.create(
            reading_list=self.mine, comic=c2, manual=True, position=1
        )
        self.hold(self.mine, "series", dashdemon, position=1)
        more[0].delete()
        sweep_live()
        reconcile_list(self.mine)
        volume = Volume.objects.get(series=dashdemon)
        back = self.make_comic(dashdemon, volume, 7)
        reconcile_list(self.mine)
        assert self.order(self.mine) == [c1.pk, back.pk, c2.pk]

    def test_blocks_sit_at_the_end_of_an_imported_list(self) -> None:
        """An imported order is not interrupted by a collection."""
        imported = import_document(_document(), _upload(), user=self.reader)
        dashdemon, more = self.make_series("Dashdemon")
        before = self.order(imported)
        self.hold(imported, "series", dashdemon, position=0)
        assert self.order(imported) == [*before, *self.pks(more)]
        assert dashdemon.pk


class RenumberTests(LiveFixture):
    """Positions change in one statement, and the cache follows."""

    def test_a_reorder_is_one_update(self) -> None:
        """New issues early in a series renumber with a single UPDATE."""
        self.hold(self.mine, "series", self.series)
        self.make_comic(self.series, self.volume, 0)
        with CaptureQueriesContext(connection) as context:
            reconcile_list(self.mine)
        updates = [
            query["sql"]
            for query in context.captured_queries
            if query["sql"].startswith("UPDATE")
            and "codex_readinglistentry" in query["sql"]
        ]
        assert len(updates) == 1, updates
        assert "json_each" in updates[0]

    def test_a_cached_read_sees_the_new_order(self) -> None:
        """Cachalot invalidates on the raw renumber alone."""

        def positions():
            return list(
                ReadingListEntry.objects.filter(reading_list=self.mine)
                .order_by("position", "pk")
                .values_list("pk", flat=True)
            )

        self.hold(self.mine, "series", self.series)
        before = positions()
        with CaptureQueriesContext(connection) as context:
            assert positions() == before
        # The read is answered from cachalot's cache, not the database.
        assert not context.captured_queries
        # Only the raw UPDATE touches the table: no ORM write to lean on.
        live.renumber(list(reversed(before)))
        assert positions() == list(reversed(before))


class SizeTests(LiveFixture):
    """A large collection is synced by a librarian job, not inline."""

    def test_large_targets_need_a_job(self) -> None:
        """Above the limit, the caller queues the sync."""
        with patch.object(live, "LIVE_INLINE_LIMIT", 3):
            assert live.is_large("series", self.series.pk)
        assert not live.is_large("series", self.series.pk)


class TriggerTests(LiveFixture):
    """What starts a live sync outside a person's edits."""

    # Every counter that may change a collection's comics.
    LIVE_COUNTERS: Final = (
        "comic",
        "link",
        "tags",
        "comics_moved",
        "folders_moved",
        "comics_deleted",
        "folders_deleted",
    )

    @staticmethod
    def _importer(counts: Counts) -> ReadingListsImporter:
        importer = ReadingListsImporter.__new__(ReadingListsImporter)
        importer.counts = counts
        importer.librarian_queue = _Queue()  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[invalid-assignment]
        importer.status_controller = MagicMock()
        importer.log = logger  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[invalid-assignment]
        return importer

    def test_each_counter_syncs_items(self) -> None:
        """One test per importer counter: each runs the live sync."""
        for name in self.LIVE_COUNTERS:
            importer = self._importer(Counts(**{name: 1}))
            with patch(_IMPORTER_SYNC_LIVE, return_value=0) as sync:
                importer.sync_reading_lists()
            assert sync.called, name

    def test_a_revival_only_import_does_not(self) -> None:
        """A revived comic kept its row and links: nothing to sync."""
        importer = self._importer(Counts(comics_revived=3, folders_revived=1))
        with patch(_IMPORTER_SYNC_LIVE, return_value=0) as sync:
            importer.sync_reading_lists()
        assert not sync.called

    def test_an_import_brings_a_new_issue_into_the_list(self) -> None:
        """The digest-gated sync picks up a new issue of a held series."""
        self.hold(self.mine, "series", self.series)
        c5 = self.make_comic(self.series, self.volume, 5)
        self._importer(Counts(comic=1)).sync_reading_lists()
        assert c5.pk in self.order(self.mine)

    def test_the_nightly_run_forces_a_sync_after_the_rematch(self) -> None:
        """Queued after the rematch, and it runs after it."""
        tasks = [type(task) for task in _NIGHTLY_TASKS]
        live_tasks = [
            task for task in _NIGHTLY_TASKS if isinstance(task, ReadingListLiveSyncTask)
        ]
        assert [task.force for task in live_tasks] == [True]
        rematch = tasks.index(JanitorRematchReadingListsTask)
        assert tasks.index(ReadingListLiveSyncTask) > rematch
        live_priority = get_task_priority(live_tasks[0])[0]
        assert live_priority > get_task_priority(JanitorRematchReadingListsTask())[0]

    def test_the_reaper_sweeps(self) -> None:
        """Reaped comics leave no comicless live rows behind."""
        with patch(_REAPER_SWEEP, return_value=0) as sweep:
            janitor = Janitor(logger, _Queue(), Lock(), Event())
            janitor.reap_pending_deletes()
        assert sweep.called


class OwnershipTests(LiveFixture):
    """An admin's private flip keeps global lists from holding personal ones."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def _flip(self, reading_list: ReadingList, *, private: bool):
        return self.client.patch(
            f"/api/v4/admin/reading-lists/{reading_list.pk}",
            data=json.dumps({"private": private}),
            content_type="application/json",
        )

    def test_a_held_global_list_stays_global(self) -> None:
        """Another global list holds it: it cannot become personal."""
        inner = ReadingList.objects.create(name="Inner")
        outer = ReadingList.objects.create(name="Outer")
        add_item(outer, "arcs", inner.pk)
        response = self._flip(inner, private=True)
        assert response.status_code == 400, response.content  # noqa: PLR2004
        inner.refresh_from_db()
        assert inner.user_id is None  # pyright: ignore[reportAttributeAccessIssue]

    def test_a_list_holding_a_personal_one_stays_personal(self) -> None:
        """It holds the admin's own list: it cannot become global."""
        own = ReadingList.objects.create(name="Own", user=self.admin)
        holder = ReadingList.objects.create(name="Holder", user=self.admin)
        add_item(holder, "arcs", own.pk)
        response = self._flip(holder, private=False)
        assert response.status_code == 400, response.content  # noqa: PLR2004

    def test_a_free_list_flips(self) -> None:
        """Nothing holds it and it holds nothing personal."""
        loose = ReadingList.objects.create(name="Loose")
        assert self._flip(loose, private=True).status_code == 200  # noqa: PLR2004

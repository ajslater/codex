"""
Code that writes a list's other entries leaves its live entries to live.py.

A recompute neither reads nor deletes live entries; it hands the list to
:func:`reconcile_list` afterwards, since the comics the list holds
otherwise may have changed. A rematch does the same.
"""

from codex.librarian.scribe.readinglists.arcs import arc_members
from codex.librarian.scribe.readinglists.combine import recombine, rematch
from codex.librarian.scribe.readinglists.live import add_item, reconcile_list
from codex.librarian.scribe.readinglists.service import (
    combine_lists,
    copy_list,
    import_document,
    rank_sources,
)
from codex.librarian.scribe.readinglists.sync import (
    is_tags_only,
    rebuild_from_tags,
    sync_tag_lists,
)
from codex.models import ReadingList, ReadingListEntry, ReadingListSource
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from codex.views.readinglists.entries import add_comics
from tests.test_reading_list_combine import _document, _upload
from tests.test_reading_list_live import LiveFixture


def _live(reading_list: ReadingList) -> list[tuple[int, int | None]]:
    """Each live entry as (pk, comic pk), in list order."""
    return list(
        ReadingListEntry.objects.filter(
            reading_list=reading_list, live_source__isnull=False
        )
        .order_by("position", "pk")
        .values_list("pk", "comic_id")
    )


def _dense(reading_list: ReadingList) -> bool:
    positions = list(
        ReadingListEntry.objects.filter(reading_list=reading_list)
        .order_by("position", "pk")
        .values_list("position", flat=True)
    )
    return positions == list(range(len(positions)))


class RecombineTests(LiveFixture):
    """A recompute keeps the live entries and their order."""

    def test_an_imported_list_keeps_its_series_through_a_recombine(self) -> None:
        """Same live rows after, at the end, positions dense."""
        imported = import_document(_document(), _upload(), user=self.reader)
        self.hold(imported, "series", self.series)
        before = _live(imported)
        assert before
        recombine(imported)
        assert _live(imported) == before
        assert _dense(imported)
        order = self.order(imported)
        assert order[-len(before) :] == [comic for _, comic in before]

    def test_the_series_skips_what_the_import_matched(self) -> None:
        """Civil War 1-3 come from the list; the series adds only #4."""
        imported = import_document(_document(), _upload(), user=self.reader)
        self.hold(imported, "series", self.series)
        recombine(imported)
        assert [comic for _, comic in _live(imported)] == [self.comics[3].pk]
        order = list(filter(None, self.order(imported)))
        assert len(order) == len(set(order))

    def test_a_hand_made_list_keeps_its_series(self) -> None:
        """No source to combine: hand rows heal, live rows stay."""
        c1 = self.comics[0]
        daredevil, more = self.make_series("Daredevil")
        add_comics(self.mine, [c1.pk])
        self.hold(self.mine, "series", daredevil)
        before = _live(self.mine)
        recombine(self.mine)
        assert _live(self.mine) == before
        assert [comic for _, comic in before] == self.pks(more)

    def test_a_collection_item_takes_a_tags_list_off_the_fast_path(self) -> None:
        """A tags list holding a series is curated: it recombines."""
        c1, c2, _, _ = self.comics
        self.tag(c1, "Civil War", 1)
        self.tag(c2, "Civil War", 2)
        sync_tag_lists()
        tags_list = ReadingList.objects.get(name="Civil War", user=None)
        assert is_tags_only(tags_list)
        daredevil, _ = self.make_series("Daredevil")
        add_item(tags_list, "series", daredevil.pk)
        assert not is_tags_only(tags_list)

    def test_a_rebuild_from_tags_leaves_live_rows(self) -> None:
        """Defensive: only the tags' own rows are replaced."""
        c1, c2, _, _ = self.comics
        self.tag(c1, "Civil War", 1)
        sync_tag_lists()
        tags_list = ReadingList.objects.get(name="Civil War", user=None)
        source = ReadingListSource.objects.get(
            reading_list=tags_list, kind=ReadingListSourceKind.TAGS
        )
        daredevil, _ = self.make_series("Daredevil")
        self.hold(tags_list, "series", daredevil)
        before = _live(tags_list)
        _, members = arc_members()
        rebuild_from_tags(tags_list, source, members[source.ref])
        assert _live(tags_list) == before
        del c2


class RematchTests(LiveFixture):
    """A rematch hands the list to the live sync after finding comics."""

    def test_a_found_comic_stops_coming_from_the_series(self) -> None:
        """Once matched by hand reference, #4 is no longer a live row."""
        c4 = self.comics[3]
        add_comics(self.mine, [c4.pk])
        ReadingListEntry.objects.filter(reading_list=self.mine, comic=c4).update(
            comic=None, match_tier=ReadingListMatchTier.NONE
        )
        self.hold(self.mine, "series", self.series)
        assert c4.pk in [comic for _, comic in _live(self.mine)]
        assert rematch(self.mine) == 1
        assert c4.pk not in [comic for _, comic in _live(self.mine)]
        assert [pk for pk in self.order(self.mine) if pk == c4.pk] == [c4.pk]

    def test_a_comicless_live_row_is_not_matched(self) -> None:
        """A live row has no reference; the sweep, not a rematch, drops it."""
        self.hold(self.mine, "series", self.series)
        ReadingListEntry.objects.filter(
            reading_list=self.mine, live_source__isnull=False
        ).update(comic=None)
        assert rematch(self.mine) == 0
        reconcile_list(self.mine)
        live = [comic for _, comic in _live(self.mine) if comic is not None]
        assert sorted(live) == self.pks(self.comics)


def _items(reading_list: ReadingList) -> list[tuple[str, int | None]]:
    return list(
        ReadingListSource.objects.filter(
            reading_list=reading_list, kind=ReadingListSourceKind.COLLECTION
        )
        .order_by("rank", "pk")
        .values_list("collection", "target_id")
    )


class CopyTests(LiveFixture):
    """A copy keeps its collection items live."""

    def test_a_copy_holds_the_series_not_its_rows(self) -> None:
        """The item is copied and synced; hand rows copy as hand rows."""
        c1 = self.comics[0]
        daredevil, more = self.make_series("Daredevil")
        add_comics(self.mine, [c1.pk])
        self.hold(self.mine, "series", daredevil)
        copy = copy_list(self.mine, user=self.reader, name="Mine again")
        assert _items(copy) == [("series", daredevil.pk)]
        assert [comic for _, comic in _live(copy)] == self.pks(more)
        manual = ReadingListEntry.objects.filter(reading_list=copy, manual=True)
        assert list(manual.values_list("comic_id", flat=True)) == [c1.pk]

    def test_a_global_copy_leaves_out_personal_lists(self) -> None:
        """A global list cannot hold a personal one, copied or not."""
        inner = ReadingList.objects.create(name="Inner", user=self.reader)
        add_comics(inner, [self.comics[0].pk])
        self.hold(self.mine, "arcs", inner)
        self.hold(self.mine, "series", self.series)
        copy = copy_list(self.mine, user=None, name="Shared")
        assert _items(copy) == [("series", self.series.pk)]


class CombineListsTests(LiveFixture):
    """Combining lists moves their items into the primary."""

    def test_an_absorbed_lists_series_moves_in(self) -> None:
        """The primary holds the other list's series, synced."""
        primary = import_document(_document(), _upload())
        other = ReadingList.objects.create(name="Other")
        daredevil, more = self.make_series("Daredevil")
        self.hold(other, "series", daredevil)
        combine_lists(primary, [other])
        assert ("series", daredevil.pk) in _items(primary)
        assert [comic for _, comic in _live(primary)] == self.pks(more)

    def test_an_item_holding_the_primary_is_dropped(self) -> None:
        """A list cannot come to hold itself by combining."""
        primary = ReadingList.objects.create(name="Primary")
        other = ReadingList.objects.create(name="Other")
        add_item(other, "arcs", primary.pk)
        combine_lists(primary, [other])
        assert _items(primary) == []

    def test_lists_holding_an_absorbed_list_hold_the_primary(self) -> None:
        """A third list's item follows the absorbed list into the primary."""
        primary = ReadingList.objects.create(name="Primary")
        other = ReadingList.objects.create(name="Other")
        holder = ReadingList.objects.create(name="Holder")
        add_item(holder, "arcs", other.pk)
        combine_lists(primary, [other])
        assert _items(holder) == [("arcs", primary.pk)]


class RankTests(LiveFixture):
    """Reordering sources leaves the items' own order alone."""

    def test_items_keep_their_ranks(self) -> None:
        """Only document and tags sources are ranked."""
        imported = import_document(_document(), _upload())
        daredevil, _ = self.make_series("Daredevil")
        first = add_item(imported, "series", self.series.pk)
        second = add_item(imported, "series", daredevil.pk)
        upload = ReadingListSource.objects.get(
            reading_list=imported, kind=ReadingListSourceKind.UPLOAD
        )
        rank_sources(imported, [upload.pk])
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.rank < second.rank

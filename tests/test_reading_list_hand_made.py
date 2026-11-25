"""
Lists without a document or tags source: copies and lists made by hand.

Such a list has nothing for comicbox to combine. A recompute must leave
its entries where they are, keep its header, and only find a hand-added
entry's comic again. Removing a list's last source deletes only a global
list that came from that source.
"""

from typing import Final, override

from django.contrib.auth.models import User

from codex.librarian.scribe.readinglists.combine import document_of, recombine
from codex.librarian.scribe.readinglists.service import (
    SourceSpec,
    copy_list,
    import_document,
    remove_source,
)
from codex.models import ReadingList, ReadingListEntry, ReadingListSource
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from codex.views.admin.reading_lists.review import _dry_run
from codex.views.readinglists.entries import add_comics
from tests.test_reading_list_combine import _CBL, _document, _upload
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_HEADER: Final = {
    "description": "Heroes take sides.",
    "list_type": "event",
    "start_year": 2006,
    "end_year": 2007,
}
_OTHER_CBL: Final = _CBL.replace("[Marvel] Civil War (CBRO)", "Front Line").replace(
    'Series="The Amazing Spider-Man" Number="532"',
    'Series="Civil War: Front Line" Number="1"',
)


def _entries(reading_list: ReadingList) -> list[tuple[int, int, int | None]]:
    """Each entry as (pk, position, comic pk), in list order."""
    return list(
        ReadingListEntry.objects.filter(reading_list=reading_list)
        .order_by("position", "pk")
        .values_list("pk", "position", "comic_id")
    )


class _HandMadeFixture(ReadingListFixture):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.original = ReadingList.objects.create(name="Civil War", **_HEADER)  # pyright: ignore[reportUninitializedInstanceVariable]
        add_comics(self.original, [comic.pk for comic in self.comics])


class CopiedListTests(_HandMadeFixture):
    """A copy is hand-made: a recompute keeps its header and its order."""

    def test_a_copy_keeps_its_header_through_a_recombine(self) -> None:
        """Description, type and years survive a recompute."""
        copy = copy_list(self.original, user=None, name="Civil War (copy)")
        recombine(copy)
        copy.refresh_from_db()
        header = {key: getattr(copy, key) for key in _HEADER}
        assert header == _HEADER

    def test_a_copy_records_the_header_it_copied(self) -> None:
        """A source added later does not overwrite the copied header."""
        copy = copy_list(self.original, user=None, name="Civil War (copy)")
        assert set(copy.edited_fields or ()) >= set(_HEADER)

    def test_a_locked_list_gaining_its_first_source_flags_nothing(self) -> None:
        """No current order to place beside: the source's matches stand."""
        copy = copy_list(self.original, user=None, name="Civil War (copy)")
        import_document(_document(), _upload(), into=copy)
        assert not ReadingListEntry.objects.filter(
            reading_list=copy, manual=False, needs_review=True
        ).exists()


class HandMadeRecombineTests(_HandMadeFixture):
    """With no source, a recompute heals hand-added entries in place."""

    def test_entries_stay_where_they_are(self) -> None:
        """Same rows, same order: nothing is deleted or moved."""
        reading_list = ReadingList.objects.create(name="Mine", order_locked=True)
        c1, c2, c3, _ = self.comics
        add_comics(reading_list, [c3.pk, c1.pk, c2.pk])
        before = _entries(reading_list)
        recombine(reading_list)
        assert _entries(reading_list) == before

    def test_a_lost_comic_is_found_again_in_place(self) -> None:
        """A hand-added entry whose comic went matches again by reference."""
        _, c2, _, _ = self.comics
        entry = ReadingListEntry.objects.get(reading_list=self.original, comic=c2)
        ReadingListEntry.objects.filter(pk=entry.pk).update(
            comic=None, match_tier=ReadingListMatchTier.NONE
        )
        recombine(self.original)
        entry.refresh_from_db()
        assert entry.comic_id == c2.pk  # pyright: ignore[reportAttributeAccessIssue]


class DisposableTests(ReadingListFixture):
    """Only a global list that came from its last source goes with it."""

    def test_a_global_list_goes_with_its_last_source(self) -> None:
        """An imported list with nothing else in it is deleted."""
        reading_list = import_document(_document(), _upload())
        source = ReadingListSource.objects.get(reading_list=reading_list)
        assert not remove_source(source)
        assert not ReadingList.objects.filter(pk=reading_list.pk).exists()

    def test_a_personal_list_stays_without_sources(self) -> None:
        """A person's list is theirs to delete, even when it is empty."""
        user = User.objects.create_user(username="reader", password=_PW)
        reading_list = import_document(_document(), _upload(), user=user)
        source = ReadingListSource.objects.get(reading_list=reading_list)
        assert remove_source(source)
        assert ReadingList.objects.filter(pk=reading_list.pk).exists()


class DocumentOfTests(ReadingListFixture):
    """An exported list carries only header extras comicbox knows."""

    def test_codex_bookkeeping_stays_out(self) -> None:
        """``written_arc`` is Codex's own note, not part of the list."""
        reading_list = ReadingList.objects.create(
            name="Civil War",
            extra={"previous": {"name": "House of M"}, "written_arc": "Civil War"},
        )
        document = document_of(reading_list)
        assert document["previous"] == {"name": "House of M"}
        assert "written_arc" not in document


class DryRunTests(ReadingListFixture):
    """A combine preview credits each list with its own entries."""

    def test_only_in_counts_go_to_the_right_lists(self) -> None:
        """An empty list in the middle does not shift the counts."""
        first = import_document(_document(), _upload())
        empty = ReadingList.objects.create(name="Empty")
        other = import_document(
            _document(_OTHER_CBL),
            SourceSpec(kind=ReadingListSourceKind.UPLOAD, ref="other"),
        )
        report = _dry_run([first, empty, other])
        only_in = {row["pk"]: row["count"] for row in report["only_in"]}
        assert only_in.get(empty.pk, 0) == 0
        assert only_in[first.pk] == 1
        assert only_in[other.pk] == 1

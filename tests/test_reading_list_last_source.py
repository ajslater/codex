"""
Removing a list's last source removes the rows it supplied (B1).

A list no source feeds took the hand-made path, which keeps the entries as
they are, so the rows of the source just removed stayed. What was added by
hand stays, a hand-added entry folded into one of those rows included.
"""

from typing import Final

from comicbox.readinglists import loads
from django.contrib.auth.models import User

from codex.librarian.scribe.readinglists.documents import to_json
from codex.librarian.scribe.readinglists.service import (
    SourceSpec,
    combine_lists,
    import_document,
    remove_source,
)
from codex.models import ReadingList, ReadingListEntry, ReadingListSource
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from codex.views.readinglists.entries import remove_comics
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"


def _cbl(*numbers: int) -> dict:
    """Return a ComicRack list of Civil War issues, stored as codex stores one."""
    books = "".join(
        f'<Book Series="Civil War" Number="{number}" Volume="2006" Year="2006" />'
        for number in numbers
    )
    text = (
        '<?xml version="1.0"?><ReadingList><Name>Civil War</Name>'
        f"<Books>{books}</Books><Matchers /></ReadingList>"
    )
    return to_json(loads(text).reading_list)


def _upload() -> SourceSpec:
    return SourceSpec(kind=ReadingListSourceKind.UPLOAD, ref="cw.cbl")


def _entries(reading_list: ReadingList):
    return ReadingListEntry.objects.filter(reading_list=reading_list).order_by(
        "position", "pk"
    )


def _comics(reading_list: ReadingList) -> list[int | None]:
    return list(_entries(reading_list).values_list("comic_id", flat=True))


def _remove_the_source(reading_list: ReadingList) -> bool:
    return remove_source(ReadingListSource.objects.get(reading_list=reading_list))


class LastSourceTests(ReadingListFixture):
    """A list loses its one source."""

    def test_a_personal_list_is_left_empty(self) -> None:
        """A person's list stays, without the issues the source brought."""
        owner = User.objects.create_user(username="owner", password=_PW)
        reading_list = import_document(_cbl(1, 2), _upload(), user=owner)
        assert _remove_the_source(reading_list)
        assert _comics(reading_list) == []

    def test_what_was_added_by_hand_stays(self) -> None:
        """A global list keeps its hand-added issue, and only that."""
        c3 = self.comics[2]
        reading_list = import_document(_cbl(1, 2), _upload())
        ReadingListEntry.objects.create(
            reading_list=reading_list,
            position=2,
            comic=c3,
            match_tier=ReadingListMatchTier.MANUAL,
            manual=True,
        )
        assert _remove_the_source(reading_list)
        assert _comics(reading_list) == [c3.pk]
        assert list(_entries(reading_list).values_list("position", flat=True)) == [0]

    def test_a_folded_entry_is_the_lists_own_again(self) -> None:
        """
        A hand-added issue the source held stays once, as the list's own.

        No source supplies it now, so removing it deletes it.
        """
        _, _, c3, _ = self.comics
        reading_list = ReadingList.objects.create(name="Hand Made")
        ReadingListEntry.objects.create(
            reading_list=reading_list,
            comic=c3,
            match_tier=ReadingListMatchTier.MANUAL,
            manual=True,
        )
        import_document(_cbl(3, 4), _upload(), into=reading_list)
        assert _remove_the_source(reading_list)
        assert _comics(reading_list) == [c3.pk]
        (entry,) = _entries(reading_list)
        assert entry.manual
        assert entry.source_ids == []
        result = remove_comics(reading_list, [c3.pk])
        assert (result["removed"], result["hidden"]) == (1, 0)


class CombineHandMadeTests(ReadingListFixture):
    """
    Combining lists no source feeds, such as two Copy to Global lists.

    Older than this branch: the sourceless path ignored the edits a combine
    passes, so the absorbed lists went and so did their entries.
    """

    def _hand_made(self, name: str, *comics) -> ReadingList:
        reading_list = ReadingList.objects.create(name=name)
        for position, comic in enumerate(comics):
            ReadingListEntry.objects.create(
                reading_list=reading_list,
                position=position,
                comic=comic,
                series_name="" if comic else "Civil War",
                issue="" if comic else "9",
                match_tier=ReadingListMatchTier.MANUAL
                if comic
                else ReadingListMatchTier.NONE,
                manual=True,
            )
        return reading_list

    def test_the_absorbed_lists_entries_come_along(self) -> None:
        """Each issue comes once, the primary's order first."""
        c1, c2, c3, _ = self.comics
        primary = self._hand_made("Primary", c1, c2)
        other = self._hand_made("Other", c2, c3, None)
        combine_lists(primary, [other])
        assert not ReadingList.objects.filter(pk=other.pk).exists()
        assert _comics(primary) == [c1.pk, c2.pk, c3.pk, None]
        assert list(_entries(primary).values_list("position", flat=True)) == [
            0,
            1,
            2,
            3,
        ]
        assert all(entry.manual for entry in _entries(primary))

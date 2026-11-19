"""
Hand edits on reading lists survive recombines, new sources and combining.

A pick, a hidden entry, an accepted guess and a "marked missing" are saved in
Codex only. A recompute finds them again by the entry's identity, which may
gain ids as sources are added.
"""

from datetime import date
from pathlib import Path
from typing import Any, Final

from codex.librarian.scribe.readinglists.combine import recombine, rematch
from codex.librarian.scribe.readinglists.service import (
    SourceSpec,
    combine_lists,
    import_document,
)
from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.models import (
    Comic,
    Imprint,
    Publisher,
    ReadingList,
    ReadingListEntry,
    Series,
    Volume,
)
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from codex.views.readinglists.entries import add_comics
from tests.test_reading_list_combine import _document, _rows, _upload
from tests.test_reading_lists import ReadingListFixture

# A Metron list holding Civil War #1 with Metron's own id. Combined with the
# Comic Vine keyed CBL, the entry gains a Metron id, which ranks first.
_METRON_DOCUMENT: Final[dict[str, Any]] = {
    "name": "Civil War",
    "sources": [{"kind": "metron-list", "key": "77"}],
    "entries": [
        {
            "series": {"name": "Civil War", "start_year": 2006},
            "volume": {"number": 2006},
            "issue": {"name": "1"},
            "date": {"year": 2006},
            "identifiers": {"metron": {"key": "9001"}},
        }
    ],
}
_METRON: Final = SourceSpec(kind=ReadingListSourceKind.METRON_LIST, ref="77")


def _entries(reading_list: ReadingList) -> list[ReadingListEntry]:
    return list(
        ReadingListEntry.objects.filter(reading_list=reading_list).order_by(
            "position", "pk"
        )
    )


def _new_comic(fixture: ReadingListFixture, name: str, number: int) -> Comic:
    """Add a comic to the fixture's series, as a later import would."""
    first = fixture.comics[0]
    path = Path(first.path).parent / f"{name}.cbz"
    path.touch()
    return Comic.objects.create(
        library=fixture.library,
        path=path,
        name=name,
        issue_number=number,
        year=2006,
        month=6 + number,
        day=1,
        date=date(2006, 6 + number, 1),
        publisher=first.publisher,
        imprint=first.imprint,
        series=first.series,
        volume=first.volume,
        parent_folder=first.parent_folder,
        size=1,
        page_count=10,
    )


class NewSourceOverlayTests(ReadingListFixture):
    """Adding a source with better ids keeps the hand edits."""

    def test_hidden_entry_survives_a_metron_source(self) -> None:
        """The Comic Vine keyed entry stays hidden once Metron's id joins it."""
        reading_list = import_document(_document(), _upload())
        first = _entries(reading_list)[0]
        first.ignored = True
        first.save()
        import_document(_METRON_DOCUMENT, _METRON, into=reading_list)
        first = _entries(reading_list)[0]
        assert "metron" in first.reference["identifiers"]
        assert first.ignored

    def test_pick_survives_a_metron_source(self) -> None:
        """A hand-picked comic stays picked once Metron's id joins the entry."""
        c4 = self.comics[3]
        reading_list = import_document(_document(), _upload())
        first = _entries(reading_list)[0]
        first.comic = c4
        first.match_tier = ReadingListMatchTier.MANUAL
        first.save()
        import_document(_METRON_DOCUMENT, _METRON, into=reading_list)
        first = _entries(reading_list)[0]
        assert (first.comic_id, first.match_tier) == (  # pyright: ignore[reportAttributeAccessIssue]
            c4.pk,
            ReadingListMatchTier.MANUAL,
        )


class AcceptedGuessTests(ReadingListFixture):
    """Accepting a best guess is not undone by a recombine."""

    def _second_civil_war(self, name: str = "Other") -> Comic:
        """Another publisher's Civil War #1 makes the match a guess."""
        publisher = Publisher.objects.create(name=name)
        imprint = Imprint.objects.create(name=name, publisher=publisher)
        series = Series.objects.create(
            name="Civil War", imprint=imprint, publisher=publisher, start_year=2006
        )
        volume = Volume.objects.create(
            name=2006, series=series, imprint=imprint, publisher=publisher
        )
        path = Path(self.comics[0].path).parent / f"{name}-cw1.cbz"
        path.touch()
        return Comic.objects.create(
            library=self.library,
            path=path,
            name=f"{name} Civil War 1",
            issue_number=1,
            year=2006,
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=1,
        )

    def test_an_accepted_guess_stays_accepted(self) -> None:
        """A guess cleared by Accept comes back with its comic, unflagged."""
        self._second_civil_war()
        reading_list = import_document(_document(), _upload())
        first = _entries(reading_list)[0]
        assert first.needs_review
        ReadingListEntry.objects.filter(reading_list=reading_list).update(
            needs_review=False
        )
        recombine(reading_list)
        again = _entries(reading_list)[0]
        assert again.comic_id == first.comic_id  # pyright: ignore[reportAttributeAccessIssue]
        assert not again.needs_review

    def test_a_new_comic_is_flagged_again(self) -> None:
        """An accepted entry that now finds another comic is flagged afresh."""
        self._second_civil_war()
        reading_list = import_document(_document(), _upload())
        ReadingListEntry.objects.filter(reading_list=reading_list).update(
            needs_review=False
        )
        first = _entries(reading_list)[0]
        Comic.objects.filter(pk=first.comic_id).delete()  # pyright: ignore[reportAttributeAccessIssue]
        self._second_civil_war("Third")
        recombine(reading_list)
        again = _entries(reading_list)[0]
        assert again.comic_id != first.comic_id  # pyright: ignore[reportAttributeAccessIssue]
        assert again.needs_review


class MarkedMissingTierTests(ReadingListFixture):
    """Marked missing is its own state; a vanished pick is open to rematch."""

    def test_marked_missing_survives(self) -> None:
        """A person's "the library has not got it" outlasts recombine and rematch."""
        reading_list = import_document(_document(), _upload())
        entry = _entries(reading_list)[0]
        entry.comic = None
        entry.match_tier = ReadingListMatchTier.MARKED_MISSING
        entry.save()
        recombine(reading_list)
        assert rematch(reading_list) == 0
        row = _rows(reading_list)[0]
        assert row[2:] == (None, ReadingListMatchTier.MARKED_MISSING)

    def test_a_vanished_pick_heals(self) -> None:
        """A hand pick whose file was removed and re-added is found again."""
        c1 = self.comics[0]
        reading_list = import_document(_document(), _upload())
        entry = _entries(reading_list)[0]
        entry.match_tier = ReadingListMatchTier.MANUAL
        entry.save()
        c1.delete()
        back = _new_comic(self, "cw1-again", 1)
        assert rematch(reading_list) == 1
        assert _entries(reading_list)[0].comic_id == back.pk  # pyright: ignore[reportAttributeAccessIssue]

    def test_a_vanished_hand_added_comic_heals_on_rematch(self) -> None:
        """A comic added by hand, removed and re-added, is found again."""
        reading_list = ReadingList.objects.create(name="Mine")
        c4 = self.comics[3]
        add_comics(reading_list, [c4.pk])
        c4.delete()
        back = _new_comic(self, "cw4-again", 4)
        assert rematch(reading_list) == 1
        assert _entries(reading_list)[0].comic_id == back.pk  # pyright: ignore[reportAttributeAccessIssue]

    def test_a_vanished_hand_added_comic_heals_on_recombine(self) -> None:
        """A recombine finds a hand-added comic again, too."""
        reading_list = import_document(_document(), _upload())
        c4 = self.comics[3]
        add_comics(reading_list, [c4.pk])
        c4.delete()
        back = _new_comic(self, "cw4-again", 4)
        recombine(reading_list)
        last = _entries(reading_list)[-1]
        assert last.manual
        assert last.comic_id == back.pk  # pyright: ignore[reportAttributeAccessIssue]


class CombineListsOverlayTests(ReadingListFixture):
    """Combining lists keeps the edits made on every one of them."""

    def test_combining_keeps_the_others_edits(self) -> None:
        """A pick and a hidden entry on the absorbed list survive the combine."""
        c1, c2, c3, c4 = self.comics
        self.tag(c1, "Civil War", 1)
        self.tag(c2, "Civil War", 2)
        sync_tag_lists()
        tags_list = ReadingList.objects.get(name="Civil War")
        other = import_document(_document(), _upload())
        entries = _entries(other)
        entries[1].comic = c4
        entries[1].match_tier = ReadingListMatchTier.MANUAL
        entries[1].save()
        entries[3].ignored = True
        entries[3].save()
        combined = combine_lists(tags_list, [other])
        rows = list(
            ReadingListEntry.objects.filter(reading_list=combined)
            .order_by("position")
            .values_list("comic_id", "match_tier", "ignored")
        )
        assert rows == [
            (c1.pk, ReadingListMatchTier.TAGGED, False),
            (c4.pk, ReadingListMatchTier.MANUAL, False),
            (c2.pk, ReadingListMatchTier.TAGGED, False),
            (c3.pk, ReadingListMatchTier.EXACT_NAME, True),
        ]

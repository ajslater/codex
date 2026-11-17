"""
Importing, matching and combining reading lists.

Lists come from comicbox, so the fixtures are real comicbox documents: a
ComicRack CBL parsed by comicbox and stored as codex stores one.
"""

from pathlib import Path
from typing import Final

from comicbox.readinglists import loads

from codex.librarian.scribe.readinglists.combine import recombine, rematch
from codex.librarian.scribe.readinglists.documents import to_json
from codex.librarian.scribe.readinglists.service import (
    SourceSpec,
    combine_lists,
    import_document,
    remove_source,
    suggest_for,
)
from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.models import (
    Comic,
    Identifier,
    IdentifierSource,
    ReadingList,
    ReadingListEntry,
    ReadingListSeriesMapping,
    ReadingListSource,
    Series,
)
from codex.models.identifier import IdentifierType
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from tests.test_reading_lists import ReadingListFixture

_CBL: Final = """<?xml version="1.0"?>
<ReadingList><Name>[Marvel] Civil War (CBRO)</Name><Books>
<Book Series="Civil War" Number="1" Volume="2006" Year="2006">
  <Database Name="cv" Series="18023" Issue="105747" /></Book>
<Book Series="The Amazing Spider-Man" Number="532" Volume="1963" Year="2006" />
<Book Series="Civil War" Number="2" Volume="2006" Year="2006" />
<Book Series="Civil War" Number="3" Volume="2006" Year="2006" />
</Books><Matchers /></ReadingList>
"""


def _document(text: str = _CBL) -> dict:
    """Parse a list as comicbox does and store it as codex does."""
    return to_json(loads(text).reading_list)


def _upload(name: str = "civil-war.cbl") -> SourceSpec:
    return SourceSpec(kind=ReadingListSourceKind.UPLOAD, ref=name)


def _rows(reading_list: ReadingList) -> list[tuple]:
    """Each entry as (series, issue, comic pk, tier), in list order."""
    return list(
        ReadingListEntry.objects.filter(reading_list=reading_list)
        .order_by("position", "pk")
        .values_list("series_name", "issue", "comic_id", "match_tier")
    )


class ImportMatchTests(ReadingListFixture):
    """An imported list finds the comics it names and keeps the rest."""

    def test_import_matches_by_name_and_keeps_missing(self) -> None:
        """Names find comics; a series the library lacks stays a placeholder."""
        c1, c2, c3, _ = self.comics
        reading_list = import_document(_document(), _upload())
        assert reading_list.name == "[Marvel] Civil War (CBRO)"
        assert reading_list.user is None
        assert _rows(reading_list) == [
            ("Civil War", "1", c1.pk, ReadingListMatchTier.EXACT_NAME),
            ("The Amazing Spider-Man", "532", None, ReadingListMatchTier.NONE),
            ("Civil War", "2", c2.pk, ReadingListMatchTier.EXACT_NAME),
            ("Civil War", "3", c3.pk, ReadingListMatchTier.EXACT_NAME),
        ]

    def test_issue_id_wins(self) -> None:
        """A comic carrying the entry's issue id is found by it."""
        c4 = self.comics[3]
        source = IdentifierSource.objects.create(name="comicvine")
        identifier = Identifier.objects.create(
            source=source, id_type=IdentifierType.ISSUE, key="105747"
        )
        c4.identifiers.add(identifier)
        reading_list = import_document(_document(), _upload())
        first = _rows(reading_list)[0]
        # The id outranks the name: #4 carries #1's id, and no name
        # rule could have chosen it.
        assert first[2:] == (c4.pk, ReadingListMatchTier.ISSUE_ID)

    def test_series_mapping_resolves_its_rows(self) -> None:
        """A saved mapping sends a list's series to a library series."""
        asm = Series.objects.create(
            name="Spider-Man",
            publisher=self.comics[0].publisher,
            imprint=self.comics[0].imprint,
        )
        path = Path(self.comics[0].path).parent / "asm532.cbz"
        path.touch()
        comic = Comic.objects.create(
            library=self.library,
            path=path,
            name="ASM 532",
            issue_number=532,
            publisher=asm.publisher,
            imprint=asm.imprint,
            series=asm,
            volume=self.comics[0].volume,
            size=1,
        )
        ReadingListSeriesMapping.objects.create(
            series_key="the amazing spider man", year=1963, series=asm
        )
        reading_list = import_document(_document(), _upload())
        assert _rows(reading_list)[1][2:] == (comic.pk, ReadingListMatchTier.MAPPING)

    def test_rematch_heals_a_missing_entry(self) -> None:
        """A comic added after the import is found by a rematch."""
        reading_list = import_document(_document(), _upload())
        comic = self.comics[0]
        ReadingListEntry.objects.filter(reading_list=reading_list).update(
            comic=None, match_tier=ReadingListMatchTier.NONE
        )
        assert rematch(reading_list) == 3  # noqa: PLR2004
        assert _rows(reading_list)[0][2] == comic.pk

    def test_one_bad_row_does_not_fail_the_list(self) -> None:
        """A row comicbox cannot read is dropped; the rest import."""
        text = _CBL.replace(
            '<Book Series="Civil War" Number="3"', '<Book Number="3"'
        ).replace('Volume="2006" Year="2006" />\n</Books>', 'Year="2006" />\n</Books>')
        reading_list = import_document(_document(text), _upload())
        assert len(_rows(reading_list)) == 3  # noqa: PLR2004


class CombineTests(ReadingListFixture):
    """Tags and curated lists combine, and come apart again."""

    def _tags_list(self) -> ReadingList:
        c1, c2, _, _ = self.comics
        self.tag(c1, "Civil War", 1)
        self.tag(c2, "Civil War", 2)
        sync_tag_lists()
        return ReadingList.objects.get(name="Civil War")

    def test_curated_list_combines_with_tags(self) -> None:
        """The curated order and placeholders, the tags' comics confirmed."""
        c1, c2, c3, _ = self.comics
        tags_list = self._tags_list()
        reading_list = import_document(_document(), _upload(), into=tags_list)
        assert reading_list.pk == tags_list.pk
        rows = _rows(reading_list)
        # Tags rank first, so their order is the backbone; the curated
        # list's own entries go in beside their neighbours.
        assert [row[2] for row in rows] == [c1.pk, None, c2.pk, c3.pk]
        assert rows[0][3] == ReadingListMatchTier.TAGGED
        assert rows[3][3] == ReadingListMatchTier.EXACT_NAME
        sources = ReadingListSource.objects.filter(reading_list=reading_list)
        assert sources.count() == 2  # noqa: PLR2004

    def test_removing_a_source_restores_the_list(self) -> None:
        """A combination is undone by removing the source it added."""
        c1, c2, _, _ = self.comics
        tags_list = self._tags_list()
        import_document(_document(), _upload(), into=tags_list)
        upload = ReadingListSource.objects.get(
            reading_list=tags_list, kind=ReadingListSourceKind.UPLOAD
        )
        assert remove_source(upload)
        assert [row[2] for row in _rows(tags_list)] == [c1.pk, c2.pk]

    def test_recombine_keeps_hand_edits(self) -> None:
        """A hand-picked comic, a hidden entry and a hand-added one survive."""
        c1, c2, c3, c4 = self.comics
        reading_list = import_document(_document(), _upload())
        entries = list(
            ReadingListEntry.objects.filter(reading_list=reading_list).order_by(
                "position"
            )
        )
        # Pick #4 for the ASM row, hide CW #3, add #4 by hand at the end.
        entries[1].comic = c4
        entries[1].match_tier = ReadingListMatchTier.MANUAL
        entries[1].save()
        entries[3].ignored = True
        entries[3].save()
        ReadingListEntry.objects.create(
            reading_list=reading_list,
            position=4,
            comic=c4,
            manual=True,
            match_tier=ReadingListMatchTier.MANUAL,
            reference={"series": {"name": "Civil War"}, "issue": {"name": "4"}},
        )
        recombine(reading_list)
        rows = list(
            ReadingListEntry.objects.filter(reading_list=reading_list)
            .order_by("position")
            .values_list("comic_id", "match_tier", "ignored", "manual")
        )
        assert rows == [
            (c1.pk, ReadingListMatchTier.EXACT_NAME, False, False),
            (c4.pk, ReadingListMatchTier.MANUAL, False, False),
            (c2.pk, ReadingListMatchTier.EXACT_NAME, False, False),
            (c3.pk, ReadingListMatchTier.EXACT_NAME, True, False),
            (c4.pk, ReadingListMatchTier.MANUAL, False, True),
        ]

    def test_locked_order_does_not_move(self) -> None:
        """After a hand reorder a recombine keeps the order it was given."""
        c1, c2, c3, _ = self.comics
        reading_list = import_document(_document(), _upload())
        entries = list(
            ReadingListEntry.objects.filter(reading_list=reading_list).order_by(
                "position"
            )
        )
        for position, entry in zip((3, 2, 1, 0), entries, strict=True):
            entry.position = position
            entry.save()
        reading_list.order_locked = True
        reading_list.save()
        recombine(reading_list)
        assert [row[2] for row in _rows(reading_list)] == [c3.pk, c2.pk, None, c1.pk]

    def test_combine_lists_merges_sources(self) -> None:
        """Combining moves the other list's sources in and deletes it."""
        tags_list = self._tags_list()
        other = import_document(_document(), _upload())
        combined = combine_lists(tags_list, [other])
        assert not ReadingList.objects.filter(pk=other.pk).exists()
        kinds = set(
            ReadingListSource.objects.filter(reading_list=combined).values_list(
                "kind", flat=True
            )
        )
        assert kinds == {ReadingListSourceKind.TAGS, ReadingListSourceKind.UPLOAD}

    def test_suggests_combining_tags_with_its_curated_list(self) -> None:
        """The tags list of an event is inside the event's curated list."""
        tags_list = self._tags_list()
        found = suggest_for(_document())
        assert [(item.pk, item.combine) for item in found] == [(tags_list.pk, True)]


class TagChangeOnCombinedListTests(ReadingListFixture):
    """A tag change recombines a list that has other sources."""

    def test_new_tag_joins_the_combined_list(self) -> None:
        """Tagging CW #3 makes the curated list's #3 entry tagged."""
        c1, c2, c3, _ = self.comics
        self.tag(c1, "Civil War", 1)
        self.tag(c2, "Civil War", 2)
        sync_tag_lists()
        tags_list = ReadingList.objects.get(name="Civil War")
        import_document(_document(), _upload(), into=tags_list)
        self.tag(c3, "Civil War", 3)
        sync_tag_lists()
        rows = _rows(tags_list)
        assert [row[2] for row in rows] == [c1.pk, None, c2.pk, c3.pk]
        assert rows[3][3] == ReadingListMatchTier.TAGGED
        assert ReadingListSource.objects.filter(reading_list=tags_list).count() == 2  # noqa: PLR2004

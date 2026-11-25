"""
Reading lists find every volume of a series name (issue 1053).

A codex series is a name and holds every volume of it; a comicbox series
is one volume run. Each volume keeps its own start year, so Burrowman (1940),
(2011) and (2016) #1 are three issues, not one.
"""

import shutil
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Final, override

from comicbox.readinglists import dumps, loads
from django.core.cache import cache
from django.db.models import Q
from django.test import TestCase

from codex.librarian.scribe.readinglists.combine import recombine
from codex.librarian.scribe.readinglists.documents import to_json
from codex.librarian.scribe.readinglists.matcher import ListMatcher
from codex.librarian.scribe.readinglists.references import comic_references
from codex.librarian.scribe.readinglists.service import SourceSpec, import_document
from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.models import (
    Comic,
    Folder,
    Identifier,
    IdentifierSource,
    Imprint,
    Library,
    Publisher,
    ReadingList,
    ReadingListEntry,
    ReadingListSeriesMapping,
    Series,
    StoryArc,
    StoryArcNumber,
    Volume,
)
from codex.models.identifier import IdentifierType
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from codex.startup import init_admin_flags
from codex.user_data import store as store_module
from codex.user_data.dump import dump_user_data
from codex.user_data.restore import restore
from codex.user_data.store import SidecarStore, reset_store_for_tests
from codex.views.readinglists.entries import add_comics
from codex.views.readinglists.lists import export_document
from tests.tmp_dirs import tmp_dir

TMP_DIR: Final = tmp_dir("codex.tests.reading_list_volumes")
_YEARS: Final = (1940, 2011, 2016)
# The issue's reproduction: every row is Burrowman #1.
_CBL: Final = """<?xml version="1.0"?>
<ReadingList><Name>Burrowman firsts</Name><Books>
<Book Series="Burrowman" Number="1" Volume="1940" Year="1940"/>
<Book Series="Burrowman" Number="1" Volume="2011" Year="2011"/>
<Book Series="Burrowman" Number="1" Volume="2016" Year="2016"/>
<Book Series="Burrowman" Number="1" Year="2016"/>
<Book Series="Burrowman" Number="1" Volume="2011"/>
<Book Series="Burrowman" Number="1" Volume="1940"/>
<Book Series="Burrowman" Number="1" Volume="2025" Year="2025"/>
</Books></ReadingList>"""
# The volume each row is, None for not in the library.
_CBL_WANTS: Final = (1940, 2011, 2016, 2016, 2011, 1940, None)


def _cbl_references(text: str = _CBL) -> list[dict[str, Any]]:
    """Parse a CBL as comicbox does and store its rows as codex does."""
    return list(to_json(loads(text).reading_list)["entries"])


def _metron(*, dated: bool) -> list[dict[str, Any]]:
    """Metron API rows: a start year, a small volume number, a cover date."""
    rows = []
    for number, start_year in enumerate(_YEARS, 1):
        row: dict[str, Any] = {
            "series": {"name": "Burrowman", "start_year": start_year},
            "volume": {"number": number},
            "issue": {"name": "1"},
        }
        if dated:
            row["date"] = {"year": start_year}
        rows.append(row)
    return rows


class BatmanFixture(TestCase):
    """One Series "Burrowman" with three volumes, each with a #1 and a #5."""

    # Volume names: the year (as a CBL tags them) or 1, 2, 3 (as Metron).
    METRON_NAMES: bool = False
    # Whether each volume knows its start year yet.
    VOLUME_YEARS: bool = True

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        self.library = Library.objects.create(path=str(TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.publisher = Publisher.objects.create(name="DC")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(name="DC", publisher=self.publisher)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.folder = Folder.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=self.library, path=str(TMP_DIR), name=TMP_DIR.name
        )
        # The importer folds every volume's start year into the series.
        self.series = self.make_series("Burrowman", 1940)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.volumes: dict[int, Volume] = {}  # pyright: ignore[reportUninitializedInstanceVariable]
        self.firsts: dict[int, Comic] = {}  # pyright: ignore[reportUninitializedInstanceVariable]
        self.fifths: dict[int, Comic] = {}  # pyright: ignore[reportUninitializedInstanceVariable]
        for index, year in enumerate(_YEARS, 1):
            name = index if self.METRON_NAMES else year
            volume = self.make_volume(
                self.series, name, year if self.VOLUME_YEARS else None
            )
            self.volumes[year] = volume
            self.firsts[year] = self.make_comic(volume, 1, year)
            self.fifths[year] = self.make_comic(volume, 5, year)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def make_series(self, name: str, start_year: int | None) -> Series:
        return Series.objects.create(
            name=name,
            imprint=self.imprint,
            publisher=self.publisher,
            start_year=start_year,
        )

    def make_volume(
        self, series: Series, name: int | None, start_year: int | None
    ) -> Volume:
        return Volume.objects.create(
            name=name,
            start_year=start_year,
            series=series,
            imprint=self.imprint,
            publisher=self.publisher,
        )

    def make_comic(self, volume: Volume, number: int, year: int) -> Comic:
        path = TMP_DIR / f"{volume.series.name}-{volume.pk}-{number}.cbz"
        path.touch()
        return Comic.objects.create(
            library=self.library,
            path=path,
            name=f"{volume.series.name} {number}",
            issue_number=number,
            year=year,
            month=1,
            day=1,
            date=date(year, 1, 1),
            publisher=self.publisher,
            imprint=self.imprint,
            series=volume.series,
            volume=volume,
            parent_folder=self.folder,
            size=1,
            page_count=10,
        )

    def wanted(self, years) -> list[int | None]:
        return [None if year is None else self.firsts[year].pk for year in years]

    @staticmethod
    def found(references) -> list[int | None]:
        return [match.comic_pk for match in ListMatcher().match(references)]


class YearNamedVolumeTests(BatmanFixture):
    """Volumes named for their years, as a CBL or ComicInfo tags them."""

    def test_every_cbl_row_finds_its_volume(self) -> None:
        """The issue's list: each row its own volume's #1, and 2025 missing."""
        matches = ListMatcher().match(_cbl_references())
        assert [m.comic_pk for m in matches] == self.wanted(_CBL_WANTS)
        assert not any(match.needs_review for match in matches)

    def test_metron_rows_find_their_volumes(self) -> None:
        """A start year finds its volume, dated or not."""
        for dated in (True, False):
            assert self.found(_metron(dated=dated)) == self.wanted(_YEARS), dated

    def test_references_carry_the_volume_start_year(self) -> None:
        """A comic's reference is its volume's year, not the series'."""
        reference = comic_references((self.firsts[2011].pk,))[self.firsts[2011].pk]
        assert reference["series"] == {"name": "Burrowman", "start_year": 2011}
        assert reference["volume"] == {"number": 2011}

    def test_series_ids_only_for_one_volume(self) -> None:
        """One id per name is at most one volume's, so it is left out."""
        source = IdentifierSource.objects.create(name="metron")
        self.series.identifier = Identifier.objects.create(
            source=source, id_type=IdentifierType.SERIES.value, key="1"
        )
        self.series.save()
        single = self.make_series("Rowan", 1993)
        rowan = self.make_comic(self.make_volume(single, None, 1993), 1, 1993)
        single.identifier = Identifier.objects.create(
            source=source, id_type=IdentifierType.SERIES.value, key="2"
        )
        single.save()
        pks = (self.firsts[2011].pk, rowan.pk)
        references = comic_references(pks)
        assert "identifiers" not in references[pks[0]]["series"]
        assert references[rowan.pk]["series"]["identifiers"] == {"metron": {"key": "2"}}


class MetronNumberedVolumeTests(BatmanFixture):
    """Volumes numbered 1, 2, 3, as MetronInfo tags them."""

    METRON_NAMES = True

    def test_metron_rows_find_their_volumes(self) -> None:
        for dated in (True, False):
            assert self.found(_metron(dated=dated)) == self.wanted(_YEARS), dated

    def test_dated_cbl_rows_find_their_volumes(self) -> None:
        """A CBL's year volume is the start year, which each volume keeps."""
        references = _cbl_references()
        assert self.found(references) == self.wanted(_CBL_WANTS)


class FoldedVolumeTests(BatmanFixture):
    """Volumes before their comics are read again: no start years yet."""

    VOLUME_YEARS = False

    def test_year_named_rows_match_at_once(self) -> None:
        """A year-like volume does the start year's job."""
        references = _cbl_references()
        assert self.found(references) == self.wanted(_CBL_WANTS)


class InterimMetronTests(BatmanFixture):
    """Metron-numbered volumes with no start years: the safety net."""

    METRON_NAMES = True
    VOLUME_YEARS = False

    def test_dated_rows_match_by_cover_year(self) -> None:
        assert self.found(_metron(dated=True)) == self.wanted(_YEARS)

    def test_a_cross_volume_tie_is_flagged(self) -> None:
        """Two volumes' #1 of one cover year: the lowest pk, for review."""
        later = self.make_volume(self.series, 4, None)
        self.make_comic(later, 1, 2011)
        (match,) = ListMatcher().match(
            [
                {
                    "series": {"name": "Burrowman"},
                    "issue": {"name": "1"},
                    "date": {"year": 2011},
                }
            ]
        )
        assert match.comic_pk == self.firsts[2011].pk
        assert match.needs_review

    def test_one_run_in_two_volume_rows_is_not_flagged(self) -> None:
        """A "v2" and a "(2011)" row are one run: they do not conflict."""
        Volume.objects.filter(pk=self.volumes[2011].pk).update(start_year=2011)
        same_run = self.make_volume(self.series, 2011, None)
        self.make_comic(same_run, 1, 2011)
        (match,) = ListMatcher().match(
            [
                {
                    "series": {"name": "Burrowman"},
                    "issue": {"name": "1"},
                    "date": {"year": 2011},
                }
            ]
        )
        assert match.comic_pk == self.firsts[2011].pk
        assert not match.needs_review


class SingleVolumeTests(BatmanFixture):
    """A series with one volume and no Volume tag keeps matching."""

    @override
    def setUp(self) -> None:
        super().setUp()
        series = self.make_series("Nightjar", 2016)
        self.nightjar = self.make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            self.make_volume(series, None, 2016), 1, 2016
        )

    def test_a_year_volume_row_without_a_year(self) -> None:
        text = """<?xml version="1.0"?><ReadingList><Name>n</Name><Books>
<Book Series="Nightjar" Number="1" Volume="2016"/></Books></ReadingList>"""
        assert self.found(_cbl_references(text)) == [self.nightjar.pk]


class MappingTests(BatmanFixture):
    """A saved series mapping finds the issue in the right volume."""

    @staticmethod
    def _map(year: int) -> None:
        series = Series.objects.get(name="Burrowman")
        ReadingListSeriesMapping.objects.create(
            series_key="the pale rook", year=year, series=series
        )

    @staticmethod
    def _entry(**extra) -> dict[str, Any]:
        reference: dict[str, Any] = {
            "series": {"name": "The Pale Rook"},
            "issue": {"name": "1"},
        }
        for key, value in extra.items():
            if key == "start_year":
                reference["series"]["start_year"] = value
            else:
                reference[key] = value
        return reference

    def test_a_mapping_for_the_2011_volume_finds_2011(self) -> None:
        self._map(2011)
        (match,) = ListMatcher().match([self._entry(start_year=2011)])
        assert match.comic_pk == self.firsts[2011].pk
        assert match.tier == ReadingListMatchTier.MAPPING
        assert not match.needs_review

    def test_a_cover_year_finds_that_years_volume(self) -> None:
        self._map(0)
        (match,) = ListMatcher().match([self._entry(date={"year": 2016})])
        assert match.comic_pk == self.firsts[2016].pk
        assert not match.needs_review

    def test_a_cover_year_one_off_finds_the_near_volume(self) -> None:
        self._map(0)
        (match,) = ListMatcher().match([self._entry(date={"year": 2012})])
        assert match.comic_pk == self.firsts[2011].pk

    def test_nothing_to_tell_volumes_by_is_flagged(self) -> None:
        self._map(0)
        (match,) = ListMatcher().match([self._entry()])
        assert match.comic_pk == self.firsts[1940].pk
        assert match.needs_review

    def test_a_wrong_start_year_falls_back_to_the_cover_year(self) -> None:
        """A list's 2012 for the library's 2011: the mapping still holds."""
        self._map(2012)
        (match,) = ListMatcher().match(
            [self._entry(start_year=2012, date={"year": 2011})]
        )
        assert match.comic_pk == self.firsts[2011].pk


class SeriesIdTests(BatmanFixture):
    """The series-id rule looks in each volume too."""

    def test_a_series_id_and_start_year_find_the_volume(self) -> None:
        source = IdentifierSource.objects.create(name="metron")
        self.series.identifier = Identifier.objects.create(
            source=source, id_type=IdentifierType.SERIES.value, key="77"
        )
        self.series.save()
        reference = {
            "series": {
                "name": "Bat-Man",
                "start_year": 2016,
                "identifiers": {"metron": {"key": "77"}},
            },
            "issue": {"name": "1"},
        }
        (match,) = ListMatcher().match([reference])
        assert match.comic_pk == self.firsts[2016].pk
        assert match.tier == ReadingListMatchTier.SERIES_ID


class CombineTests(BatmanFixture):
    """A tagged comic joins its own volume's row of a fetched list."""

    def test_the_tagged_2011_comic_lands_on_the_2011_row(self) -> None:
        arc, _ = StoryArc.objects.get_or_create(name="Fives")
        for year in (1940, 2011):
            san, _ = StoryArcNumber.objects.get_or_create(story_arc=arc, number=year)
            self.fifths[year].story_arc_numbers.add(san)
        sync_tag_lists()
        tags_list = ReadingList.objects.get(name="Fives")
        text = """<?xml version="1.0"?><ReadingList><Name>Fives</Name><Books>
<Book Series="Burrowman" Number="5" Volume="1940" Year="1940"/>
<Book Series="Burrowman" Number="5" Volume="2011" Year="2011"/>
</Books></ReadingList>"""
        import_document(
            to_json(loads(text).reading_list),
            SourceSpec(kind=ReadingListSourceKind.UPLOAD, ref="fives.cbl"),
            into=tags_list,
        )
        rows = list(
            ReadingListEntry.objects.filter(reading_list=tags_list)
            .order_by("position")
            .values_list("reference__volume__number", "comic_id")
        )
        assert rows == [(1940, self.fifths[1940].pk), (2011, self.fifths[2011].pk)]


class ExportTests(BatmanFixture):
    """A hand-added Burrowman (2011) #1 exports as Volume="2011"."""

    def _exported_volume(self, reading_list: ReadingList) -> str:
        text = dumps(export_document(reading_list, Q()), "cbl")
        return text.split('Volume="')[1].split('"')[0]

    def test_a_new_hand_entry(self) -> None:
        reading_list = ReadingList.objects.create(name="Mine")
        add_comics(reading_list, [self.firsts[2011].pk])
        assert self._exported_volume(reading_list) == "2011"

    def test_an_entry_0062_rewrote(self) -> None:
        """The folded 1940 gone, the year-like volume speaks for itself."""
        reading_list = ReadingList.objects.create(name="Mine")
        ReadingListEntry.objects.create(
            reading_list=reading_list,
            comic=self.firsts[2011],
            reference={
                "series": {"name": "Burrowman"},
                "volume": {"number": 2011},
                "issue": {"name": "1"},
            },
            match_tier=ReadingListMatchTier.MANUAL,
            manual=True,
        )
        recombine(reading_list)
        assert self._exported_volume(reading_list) == "2011"


class RestoreTests(BatmanFixture):
    """A dump from before migration 0062 restores without folded years."""

    @override
    def setUp(self) -> None:
        super().setUp()
        config = TMP_DIR / "config"
        config.mkdir(parents=True, exist_ok=True)
        self.store = SidecarStore(config / "user_data.sqlite")  # pyright: ignore[reportUninitializedInstanceVariable]
        store_module._store = self.store  # noqa: SLF001

    @override
    def tearDown(self) -> None:
        self.store.close()
        reset_store_for_tests(None)
        super().tearDown()

    def _snapshot(self) -> Path:
        dump_user_data()
        self.store.connection().execute("PRAGMA wal_checkpoint(FULL)")
        snapshot = TMP_DIR / "config" / "snapshot.sqlite"
        with sqlite3.connect(snapshot) as dst:
            self.store.connection().backup(dst)
        return snapshot

    def test_flattened_references_restore_unfolded(self) -> None:
        reading_list = ReadingList.objects.create(name="Mine")
        rows = (
            # Rule 1: a year volume that is not the start year.
            ({"start_year": 1940}, {"number": 2011}, "1", self.firsts[2011]),
            # Rule 3: a hand entry with the series' folded year.
            ({"start_year": 1940}, None, "9", None),
            # A consistent row is left alone.
            ({"start_year": 2016}, {"number": 2016}, "1", self.firsts[2016]),
        )
        for position, (series, volume, issue, comic) in enumerate(rows):
            reference: dict[str, Any] = {
                "series": {"name": "Burrowman", **series},
                "issue": {"name": issue},
            }
            if volume:
                reference["volume"] = volume
            ReadingListEntry.objects.create(
                reading_list=reading_list,
                position=position,
                comic=comic,
                reference=reference,
                match_tier=ReadingListMatchTier.MANUAL,
                manual=True,
            )
        snapshot = self._snapshot()
        ReadingList.objects.all().delete()
        restore(sidecar_path=snapshot)
        restored = ReadingList.objects.get(name="Mine")
        series = [
            entry.reference["series"]
            for entry in ReadingListEntry.objects.filter(
                reading_list=restored
            ).order_by("position")
        ]
        assert series == [
            {"name": "Burrowman"},
            {"name": "Burrowman"},
            {"name": "Burrowman", "start_year": 2016},
        ]

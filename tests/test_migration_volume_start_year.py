"""
Migration 0062 moves start years from series to volumes (issue 1053).

It backfills a series' only volume, rewrites the reading list references
codex built from the folded year, clears matches that may be another
volume's, and leaves the librarian a one-time re-read to do.
"""

from datetime import date
from typing import Any, Final, override

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from codex.librarian.scribe.readinglists.combine import rematch
from codex.librarian.scribe.readinglists.matcher import ListMatcher
from codex.models import ReadingList, ReadingListEntry, Timestamp

_BEFORE: Final = [("codex", "0061_reading_lists_and_versedb_key")]


def _latest() -> list[tuple[str, str]]:
    return MigrationExecutor(connection).loader.graph.leaf_nodes("codex")


def _migrate(target):
    MigrationExecutor(connection).migrate(target)
    return MigrationExecutor(connection).loader.project_state(target).apps


def _objects(apps, name: str) -> Any:
    return apps.get_model("codex", name).objects


def _ref(
    series: str,
    issue: int,
    start_year: int | None = None,
    volume: int | None = None,
    **series_extra,
) -> dict[str, Any]:
    reference: dict[str, Any] = {
        "series": {"name": series, **series_extra},
        "issue": {"name": str(issue)},
    }
    if start_year is not None:
        reference["series"]["start_year"] = start_year
    if volume is not None:
        reference["volume"] = {"number": volume}
    return reference


class _Seed:
    """A library as the importer left it before 0062: years folded."""

    def __init__(self, apps) -> None:
        self.apps = apps
        self.library = _objects(apps, "Library").create(path="/comics")
        self.publisher = _objects(apps, "Publisher").create(name="DC")
        self.imprint = _objects(apps, "Imprint").create(
            name="DC", publisher=self.publisher
        )
        batman = self._series("Batman", 1940)
        self.b1940 = self._comic(self._volume(batman, 1940), 1, 1940)
        self.b2011 = self._comic(self._volume(batman, 2011), 1, 2011)
        superman = self._series("Superman", 1939)
        source = _objects(apps, "IdentifierSource").create(name="comicvine")
        superman.identifier = _objects(apps, "Identifier").create(
            source=source, id_type="series", key="123"
        )
        superman.save()
        self.s1 = self._comic(self._volume(superman, 1), 1, 1939)
        self.s2 = self._comic(self._volume(superman, 2), 1, 1987)
        self.robin_volume = self._volume(self._series("Robin", 1993), None)
        self.robin = self._comic(self.robin_volume, 1, 1993)
        # One volume named for another year than the series': a deleted
        # volume's year, likely.
        self.nightwing_volume = self._volume(self._series("Nightwing", 1996), 2016)
        self.reading_list = _objects(apps, "ReadingList").create(name="Mixed")
        self.position = 0

    def _series(self, name: str, start_year: int):
        return _objects(self.apps, "Series").create(
            name=name,
            sort_name=name.lower(),
            start_year=start_year,
            publisher=self.publisher,
            imprint=self.imprint,
        )

    def _volume(self, series, name: int | None):
        return _objects(self.apps, "Volume").create(
            name=name, publisher=self.publisher, imprint=self.imprint, series=series
        )

    def _comic(self, volume, number: int, year: int):
        return _objects(self.apps, "Comic").create(
            library=self.library,
            path=f"/comics/{volume.series.name}-{volume.pk}-{number}.cbz",
            name=f"{volume.series.name} {number}",
            publisher=self.publisher,
            imprint=self.imprint,
            series=volume.series,
            volume=volume,
            issue_number=number,
            date=date(year, 1, 1),
            year=year,
            size=1,
        )

    def entry(self, reference, comic=None, tier: str = "", *, manual=False) -> int:
        self.position += 1
        return (
            _objects(self.apps, "ReadingListEntry")
            .create(
                reading_list=self.reading_list,
                position=self.position,
                comic=comic,
                reference=reference,
                match_tier=tier,
                manual=manual,
            )
            .pk
        )


def _reference(pk: int) -> dict[str, Any]:
    return ReadingListEntry.objects.get(pk=pk).reference


def _match(pk: int) -> tuple[int | None, str]:
    return ReadingListEntry.objects.values_list("comic_id", "match_tier").get(pk=pk)


class VolumeStartYearMigrationTests(TransactionTestCase):
    """Migrate a seeded 0061 library and check each step."""

    @override
    def setUp(self) -> None:
        self.addCleanup(_migrate, _latest())
        self.seed = _Seed(_migrate(_BEFORE))  # pyright: ignore[reportUninitializedInstanceVariable]

    def _migrate(self) -> Any:
        return _migrate(_latest())

    def test_backfill(self) -> None:
        """Only a series' only volume, unless it is named for another year."""
        apps = self._migrate()
        years = dict(
            _objects(apps, "Volume")
            .values_list("series__name", "start_year")
            .filter(series__name__in=("Robin", "Nightwing"))
        )
        assert years == {"Robin": 1993, "Nightwing": None}
        multi = _objects(apps, "Volume").filter(series__name__in=("Batman", "Superman"))
        assert set(multi.values_list("start_year", flat=True)) == {None}

    def test_rule_1(self) -> None:
        """A year-like volume that differs from the start year: year gone."""
        seed = self.seed
        flattened = _ref("Batman", 1, 1940, 2011)
        linked = seed.entry(flattened, seed.b2011, "manual", manual=True)
        unlinked = seed.entry(flattened)
        self._migrate()
        for pk in (linked, unlinked):
            assert _reference(pk) == _ref("Batman", 1, volume=2011)

    def test_rule_2(self) -> None:
        """A linked hand or tagged entry takes its volume's year, or none."""
        seed = self.seed
        ids = {"identifiers": {"comicvine": {"key": "123"}}}
        hand = seed.entry(_ref("Superman", 1, 1939, 2, **ids), seed.s2, manual=True)
        tagged = seed.entry(_ref("Superman", 1, 1939, 1), seed.s1, "tagged")
        robin = seed.entry(_ref("Robin", 1, 1993), seed.robin, "tagged")
        self._migrate()
        assert _reference(hand) == _ref("Superman", 1, volume=2)
        assert _reference(tagged) == _ref("Superman", 1, volume=1)
        assert _reference(robin) == _ref("Robin", 1, 1993)

    def test_rule_3(self) -> None:
        """An unlinked hand entry loses a same-named multi-volume year."""
        seed = self.seed
        hand = seed.entry(_ref("Superman", 3, 1939, 2), manual=True)
        self._migrate()
        assert _reference(hand) == _ref("Superman", 3, volume=2)

    def test_other_references_are_left_alone(self) -> None:
        """A consistent CBL row copied by hand, and an imported row."""
        seed = self.seed
        copied = _ref("Batman", 1, 2011, 2011)
        copied_pk = seed.entry(copied, manual=True)
        imported = _ref("Superman", 9, 1939, 1)
        imported_pk = seed.entry(imported)
        self._migrate()
        assert _reference(copied_pk) == copied
        assert _reference(imported_pk) == imported

    def test_reset_and_rematch(self) -> None:
        """A name match in a multi-volume series matches its own volume again."""
        seed = self.seed
        wrong = seed.entry(_ref("Batman", 1, 2011, 2011), seed.b1940, "exact_name")
        by_hand = seed.entry(_ref("Batman", 1), seed.b1940, "manual", manual=True)
        self._migrate()
        assert _match(wrong) == (None, "")
        assert _match(by_hand) == (seed.b1940.pk, "manual")

        rematch(ReadingList.objects.get(pk=seed.reading_list.pk), ListMatcher())
        assert _match(wrong) == (seed.b2011.pk, "exact_name")

    def test_marks_the_re_read_pending(self) -> None:
        self._migrate()
        key = Timestamp.Choices.VOLUME_START_YEARS.value
        assert Timestamp.objects.get(key=key).value == "pending"

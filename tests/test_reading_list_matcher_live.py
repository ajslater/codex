"""
The matcher prefers a comic the library still has to one pending delete.

A moved file leaves its old row stamped ``missing_since`` until the reap,
beside the new row the import made. Matching by lowest pk alone picked the
stamped row, which nobody can see and the reap then deletes. A stamped
comic is still matched when it is the only one, so a list survives a share
that is briefly unmounted.
"""

from comicbox.readinglists import loads, normalize_series
from django.utils import timezone

from codex.librarian.scribe.readinglists.documents import ENTRIES_KEY, to_json
from codex.librarian.scribe.readinglists.matcher import ListMatcher
from codex.models import (
    Comic,
    Identifier,
    IdentifierSource,
    Imprint,
    Publisher,
    ReadingListSeriesMapping,
    Series,
    Volume,
)
from codex.models.identifier import IdentifierType
from codex.models.readinglist import ReadingListMatchTier
from tests.test_reading_lists import TMP_DIR, ReadingListFixture

_CIVIL_WAR_1 = {
    "series": {"name": "Civil War"},
    "issue": {"name": "1"},
    "date": {"year": 2006},
}
_CIVIL_WAR_1_CV = """<?xml version="1.0"?>
<ReadingList><Name>Civil War</Name><Books>
<Book Series="Civil War" Number="1" Volume="2006" Year="2006">
  <Database Name="cv" Series="18023" Issue="105747" /></Book>
</Books><Matchers /></ReadingList>
"""
_MAPPED_1 = {
    "series": {"name": "Guerra Civil", "start_year": 2006},
    "issue": {"name": "1"},
}


class LiveComicTests(ReadingListFixture):
    """A pending-delete comic loses a tie to the live copy of the issue."""

    def _moved(self) -> tuple[Comic, Comic]:
        """Stamp the first comic missing and make its live copy, a later pk."""
        stamped = self.comics[0]
        Comic.objects.filter(pk=stamped.pk).update(missing_since=timezone.now())
        path = TMP_DIR / "moved-cw1.cbz"
        path.touch()
        live = Comic.objects.create(
            library=self.library,
            path=path,
            name=stamped.name,
            issue_number=stamped.issue_number,
            year=stamped.year,
            date=stamped.date,
            publisher=stamped.publisher,
            imprint=stamped.imprint,
            series=stamped.series,
            volume=stamped.volume,
            parent_folder=stamped.parent_folder,
            size=1,
            page_count=10,
        )
        assert live.pk > stamped.pk
        return stamped, live

    def test_a_name_match_takes_the_live_copy(self) -> None:
        """The name match picks the comic still in the library."""
        _, live = self._moved()
        (match,) = ListMatcher().match([_CIVIL_WAR_1])
        assert match.comic_pk == live.pk

    def test_a_mapped_match_takes_the_live_copy(self) -> None:
        """A series mapping picks the comic still in the library."""
        stamped, live = self._moved()
        ReadingListSeriesMapping.objects.create(
            series_key=normalize_series("Guerra Civil"),
            year=2006,
            series=stamped.series,
        )
        (match,) = ListMatcher().match([_MAPPED_1])
        assert (match.comic_pk, match.tier) == (live.pk, ReadingListMatchTier.MAPPING)

    def test_the_only_copy_still_matches_while_stamped(self) -> None:
        """With no live copy the stamped comic is matched, to survive revival."""
        stamped = self.comics[0]
        Comic.objects.filter(pk=stamped.pk).update(missing_since=timezone.now())
        (match,) = ListMatcher().match([_CIVIL_WAR_1])
        assert match.comic_pk == stamped.pk

    def test_a_stronger_match_beats_a_live_stranger(self) -> None:
        """
        Live first only among equally sure matches.

        While the list's own comic, found by its issue id, is stamped (a
        share unmounted), a different live comic found only by name must
        not take the entry: a rematch never looks at it again.
        """
        stamped = self.comics[0]
        source = IdentifierSource.objects.create(name="comicvine")
        stamped.identifiers.add(
            Identifier.objects.create(
                source=source, id_type=IdentifierType.ISSUE, key="105747"
            )
        )
        Comic.objects.filter(pk=stamped.pk).update(missing_since=timezone.now())
        publisher = Publisher.objects.create(name="Panini")
        imprint = Imprint.objects.create(name="Panini", publisher=publisher)
        series = Series.objects.create(
            name="Civil War", publisher=publisher, imprint=imprint
        )
        volume = Volume.objects.create(
            name=2006, series=series, imprint=imprint, publisher=publisher
        )
        path = TMP_DIR / "other-cw1.cbz"
        path.touch()
        Comic.objects.create(
            library=self.library,
            path=path,
            name="Civil War 1",
            issue_number=1,
            year=2006,
            date=stamped.date,
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            parent_folder=stamped.parent_folder,
            size=1,
            page_count=10,
        )
        (reference,) = to_json(loads(_CIVIL_WAR_1_CV).reading_list)[ENTRIES_KEY]
        (match,) = ListMatcher().match([reference])
        assert (match.comic_pk, match.tier) == (
            stamped.pk,
            ReadingListMatchTier.ISSUE_ID,
        )

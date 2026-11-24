"""
The matcher prefers a comic the library still has to one pending delete.

A moved file leaves its old row stamped ``missing_since`` until the reap,
beside the new row the import made. Matching by lowest pk alone picked the
stamped row, which nobody can see and the reap then deletes. A stamped
comic is still matched when it is the only one, so a list survives a share
that is briefly unmounted.
"""

from comicbox.readinglists import normalize_series
from django.utils import timezone

from codex.librarian.scribe.readinglists.matcher import ListMatcher
from codex.models import Comic, ReadingListSeriesMapping
from codex.models.readinglist import ReadingListMatchTier
from tests.test_reading_lists import TMP_DIR, ReadingListFixture

_CIVIL_WAR_1 = {
    "series": {"name": "Civil War"},
    "issue": {"name": "1"},
    "date": {"year": 2006},
}
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
            series_key=normalize_series("Guerra Civil"), year=2006, series=stamped.series
        )
        (match,) = ListMatcher().match([_MAPPED_1])
        assert (match.comic_pk, match.tier) == (live.pk, ReadingListMatchTier.MAPPING)

    def test_the_only_copy_still_matches_while_stamped(self) -> None:
        """With no live copy the stamped comic is matched, to survive revival."""
        stamped = self.comics[0]
        Comic.objects.filter(pk=stamped.pk).update(missing_since=timezone.now())
        (match,) = ListMatcher().match([_CIVIL_WAR_1])
        assert match.comic_pk == stamped.pk

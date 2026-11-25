"""
A missing issue comicbox refused in the library is suggested for review.

comicbox reports a comic it refused for an entry left missing: one of the
entry's name, issue and cover year in another volume, or of its name key
with a cover year more than one off. The entry stays missing, holds the
comic as a suggestion and is flagged, so it shows in review instead of
looking absent from the library. And an entry with only a volume number
meets a comic that has a start year and that volume.
"""

import json
from typing import Any, Final, override

from comicbox.readinglists import loads
from django.contrib.auth.models import User
from django.test import Client

from codex.librarian.scribe.readinglists.combine import rematch
from codex.librarian.scribe.readinglists.documents import to_json
from codex.librarian.scribe.readinglists.matcher import ListMatcher
from codex.librarian.scribe.readinglists.overlay import Overlay, reference_identity
from codex.librarian.scribe.readinglists.service import SourceSpec, import_document
from codex.models import ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from tests.test_reading_list_volumes import BatmanFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_LISTS: Final = "/api/v4/reading-lists"


def _batman(**fields) -> dict[str, Any]:
    reference: dict[str, Any] = {
        "series": {"name": "Burrowman"},
        "issue": {"name": "1"},
    }
    if (start_year := fields.get("start_year")) is not None:
        reference["series"]["start_year"] = start_year
    if (volume := fields.get("volume")) is not None:
        reference["volume"] = {"number": volume}
    if (year := fields.get("year")) is not None:
        reference["date"] = {"year": year}
    return reference


def _cbl(*books: str) -> dict:
    text = (
        '<?xml version="1.0"?><ReadingList><Name>Refused</Name><Books>'
        + "".join(books)
        + "</Books></ReadingList>"
    )
    return to_json(loads(text).reading_list)


class RefusedMatcherTests(BatmanFixture):
    """What the matcher answers for an entry comicbox refused comics for."""

    def test_another_volume_of_the_cover_year_is_suggested(self) -> None:
        """A 2012 volume the library lacks, dated 2011: the 2011 #1."""
        (match,) = ListMatcher().match([_batman(start_year=2012, year=2011)])
        assert match.comic_pk is None
        assert match.suggested_pk == self.firsts[2011].pk
        assert match.needs_review

    def test_a_cover_year_far_off_is_suggested(self) -> None:
        """The 2011 volume's #1, but dated 2014."""
        (match,) = ListMatcher().match([_batman(start_year=2011, year=2014)])
        assert match.comic_pk is None
        assert match.suggested_pk == self.firsts[2011].pk
        assert match.needs_review

    def test_a_volume_the_library_lacks_suggests_nothing(self) -> None:
        """Only the number in another volume and year: not a suggestion."""
        (match,) = ListMatcher().match([_batman(volume=2025, year=2025)])
        assert (match.comic_pk, match.suggested_pk, match.needs_review) == (
            None,
            None,
            False,
        )

    def test_a_found_entry_has_no_suggestion(self) -> None:
        (match,) = ListMatcher().match([_batman(start_year=2016, year=2016)])
        assert match.comic_pk == self.firsts[2016].pk
        assert match.suggested_pk is None


class VolumeKeyTests(BatmanFixture):
    """Metron-numbered volumes that know their start years."""

    METRON_NAMES = True

    def test_an_undated_volume_only_entry_finds_its_volume(self) -> None:
        """Volume 2 meets the start-year-2011 volume 2: no cover year needed."""
        (match,) = ListMatcher().match([_batman(volume=2)])
        assert match.comic_pk == self.firsts[2011].pk
        assert not match.needs_review


class RefusedEntryTests(BatmanFixture):
    """A suggestion is stored on the entry and answered in review."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def _import(self) -> ReadingList:
        return import_document(
            _cbl(
                '<Book Series="Burrowman" Number="1" Volume="2012" Year="2011"/>',
                '<Book Series="Burrowman" Number="1" Volume="2016" Year="2016"/>',
            ),
            SourceSpec(kind=ReadingListSourceKind.UPLOAD, ref="refused.cbl"),
        )

    def _rows(self, reading_list: ReadingList) -> list[tuple]:
        return list(
            ReadingListEntry.objects.filter(reading_list=reading_list)
            .order_by("position")
            .values_list("comic_id", "suggested_comic_id", "needs_review")
        )

    def _entries(self, reading_list: ReadingList) -> list[dict]:
        response = self.client.get(f"{_LISTS}/{reading_list.pk}/entries")
        assert response.status_code == _OK, response.content
        return response.json()["data"]["entries"]

    def test_an_import_stores_the_suggestion_for_review(self) -> None:
        reading_list = self._import()
        assert self._rows(reading_list) == [
            (None, self.firsts[2011].pk, True),
            (self.firsts[2016].pk, None, False),
        ]
        first, _ = self._entries(reading_list)
        assert first["comic"] is None
        assert first["needsReview"]
        assert first["suggestedComic"]["pk"] == self.firsts[2011].pk

    def test_using_the_suggestion_picks_it(self) -> None:
        reading_list = self._import()
        first, _ = self._entries(reading_list)
        response = self.client.patch(
            f"{_LISTS}/{reading_list.pk}/entries/{first['pk']}",
            data=json.dumps({"comic": self.firsts[2011].pk}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        entry = ReadingListEntry.objects.get(pk=first["pk"])
        assert (entry.comic_id, entry.suggested_comic_id, entry.needs_review) == (  # pyright: ignore[reportAttributeAccessIssue]
            self.firsts[2011].pk,
            None,
            False,
        )
        assert entry.match_tier == ReadingListMatchTier.MANUAL

    def test_accept_all_leaves_a_suggestion_for_a_person(self) -> None:
        reading_list = self._import()
        response = self.client.post(f"{_LISTS}/{reading_list.pk}/entries/accept")
        assert response.status_code == _OK, response.content
        assert self._rows(reading_list)[0] == (None, self.firsts[2011].pk, True)

    def test_a_rematch_suggests_and_then_finds(self) -> None:
        """A missing entry gains a suggestion, then its own comic clears it."""
        reading_list = ReadingList.objects.create(name="Hand")
        entry = ReadingListEntry.objects.create(
            reading_list=reading_list,
            reference=_batman(start_year=2012, year=2011),
        )
        assert rematch(reading_list) == 0
        entry.refresh_from_db()
        assert (entry.suggested_comic_id, entry.needs_review) == (  # pyright: ignore[reportAttributeAccessIssue]
            self.firsts[2011].pk,
            True,
        )
        volume = self.make_volume(self.series, 2012, 2012)
        own = self.make_comic(volume, 1, 2011)
        assert rematch(reading_list) == 1
        entry.refresh_from_db()
        assert (entry.comic_id, entry.suggested_comic_id) == (own.pk, None)  # pyright: ignore[reportAttributeAccessIssue]


class OverlayVolumeTests(BatmanFixture):
    """A hand edit stays with its own volume, though the two share a key."""

    def test_an_edit_of_another_volume_is_not_assigned(self) -> None:
        reading_list = ReadingList.objects.create(name="Two v1s")
        ReadingListEntry.objects.create(
            reading_list=reading_list,
            reference=_batman(start_year=1940, volume=1),
            match_tier=ReadingListMatchTier.MARKED_MISSING,
        )
        overlay = Overlay.of(ReadingListEntry.objects.filter(reading_list=reading_list))
        same = reference_identity(_batman(start_year=1940, volume=1))
        other = reference_identity(_batman(start_year=2011, volume=1))
        assert same.keys & other.keys, "the two share the volume key"
        assert overlay.assign([other]) == [None]
        assert overlay.assign([same]) == [0]

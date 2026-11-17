"""
Reading lists behind the ``arcs`` collection.

The sync builds one list per story-arc name from the tags and keeps it in
step. Every read of the ``arcs`` collection shows global lists and the
viewer's own, never another user's.
"""

import json
import shutil
from datetime import date
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.models import (
    Bookmark,
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    ReadingList,
    ReadingListEntry,
    ReadingListSource,
    Series,
    StoryArc,
    StoryArcNumber,
    Volume,
)
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from codex.models.shelf import Shelf, ShelfItem
from codex.startup import init_admin_flags
from codex.views.browser.cover import _resolve_collection_comic_pk
from tests.tmp_dirs import tmp_dir

TMP_DIR: Final = tmp_dir("codex.tests.reading_lists")
_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_NOT_FOUND: Final = 404
_SHOW_ALL: Final = {
    "publishers": True,
    "imprints": True,
    "series": True,
    "volumes": True,
}


class ReadingListFixture(TestCase):
    """Four comics in one series, ready to tag with arcs."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        self.library = Library.objects.create(path=str(TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        publisher = Publisher.objects.create(name="Marvel")
        imprint = Imprint.objects.create(name="Marvel", publisher=publisher)
        series = Series.objects.create(
            name="Civil War", imprint=imprint, publisher=publisher, start_year=2006
        )
        volume = Volume.objects.create(
            name=2006, series=series, imprint=imprint, publisher=publisher
        )
        folder = Folder.objects.create(
            library=self.library, path=str(TMP_DIR), name=TMP_DIR.name
        )
        self.comics = []  # pyright: ignore[reportUninitializedInstanceVariable]
        for number in range(1, 5):
            path = TMP_DIR / f"cw{number}.cbz"
            path.touch()
            self.comics.append(
                Comic.objects.create(
                    library=self.library,
                    path=path,
                    name=f"Civil War {number}",
                    issue_number=number,
                    year=2006,
                    month=6 + number,
                    day=1,
                    date=date(2006, 6 + number, 1),
                    publisher=publisher,
                    imprint=imprint,
                    series=series,
                    volume=volume,
                    parent_folder=folder,
                    size=1,
                    page_count=10,
                )
            )

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    @staticmethod
    def tag(comic: Comic, arc_name: str, number: int | None) -> None:
        """Tag a comic with an arc, as the importer links one."""
        arc, _ = StoryArc.objects.get_or_create(name=arc_name)
        san, _ = StoryArcNumber.objects.get_or_create(story_arc=arc, number=number)
        comic.story_arc_numbers.add(san)

    @staticmethod
    def untag(comic: Comic) -> None:
        """Remove every arc from a comic."""
        comic.story_arc_numbers.clear()

    @staticmethod
    def order(reading_list: ReadingList) -> list[int]:
        """Return the list's comic pks in list order."""
        return list(
            ReadingListEntry.objects.filter(reading_list=reading_list)
            .order_by("position", "pk")
            .values_list("comic_id", flat=True)
        )


class TagSyncTests(ReadingListFixture):
    """The lists from tags follow the tags."""

    def test_new_arc_makes_a_list_in_arc_order(self) -> None:
        """Arc numbers order the list; every entry is tagged and referenced."""
        c1, c2, c3, _ = self.comics
        self.tag(c1, "Civil War", 3)
        self.tag(c2, "Civil War", 1)
        self.tag(c3, "Civil War", 2)
        counts = sync_tag_lists()
        assert counts.created == 1
        reading_list = ReadingList.objects.get(name="Civil War")
        assert reading_list.user is None
        assert self.order(reading_list) == [c2.pk, c3.pk, c1.pk]
        entry = ReadingListEntry.objects.get(reading_list=reading_list, comic=c2)
        assert entry.match_tier == ReadingListMatchTier.TAGGED
        assert (entry.series_name, entry.issue, entry.year) == ("Civil War", "2", 2006)
        assert entry.reference["series"] == {"name": "Civil War", "start_year": 2006}
        assert entry.reference["issue"] == {"name": "2"}
        source = ReadingListSource.objects.get(reading_list=reading_list)
        assert source.kind == ReadingListSourceKind.TAGS
        assert source.ordered is True

    def test_unnumbered_comics_read_first_then_by_date(self) -> None:
        """NULL numbers sort first, as SQLite sorted arc browse; then date."""
        c1, c2, c3, c4 = self.comics
        self.tag(c4, "Event", None)
        self.tag(c3, "Event", None)
        self.tag(c1, "Event", 1)
        self.tag(c2, "Event", 1)
        sync_tag_lists()
        reading_list = ReadingList.objects.get(name="Event")
        assert self.order(reading_list) == [c3.pk, c4.pk, c1.pk, c2.pk]
        assert ReadingListSource.objects.get(reading_list=reading_list).ordered is False

    def test_unchanged_tags_change_nothing(self) -> None:
        """A second sync with the same tags touches no list."""
        self.tag(self.comics[0], "Civil War", 1)
        sync_tag_lists()
        assert sync_tag_lists().changed == 0

    def test_renumbering_reorders_the_same_list(self) -> None:
        """A renumbered arc reorders its list in place, keeping its pk."""
        c1, c2, _, _ = self.comics
        self.tag(c1, "Civil War", 1)
        self.tag(c2, "Civil War", 2)
        sync_tag_lists()
        reading_list = ReadingList.objects.get(name="Civil War")
        shelf = Shelf.objects.create(
            user=User.objects.create_user(username="fan", password=_PW), name="Want"
        )
        ShelfItem.objects.create(
            shelf=shelf, collection="arcs", target_id=reading_list.pk
        )
        self.untag(c1)
        self.untag(c2)
        self.tag(c1, "Civil War", 2)
        self.tag(c2, "Civil War", 1)
        assert sync_tag_lists().updated == 1
        reading_list.refresh_from_db()
        assert self.order(reading_list) == [c2.pk, c1.pk]
        assert ShelfItem.objects.filter(target_id=reading_list.pk).exists()

    def test_gone_arc_deletes_its_list(self) -> None:
        """A list whose arc is gone and holds nothing by hand is deleted."""
        c1 = self.comics[0]
        self.tag(c1, "Civil War", 1)
        sync_tag_lists()
        self.untag(c1)
        assert sync_tag_lists().deleted == 1
        assert not ReadingList.objects.exists()

    def test_hand_added_entry_keeps_the_list(self) -> None:
        """A list with an entry added by hand outlives its arc."""
        c1, c2, _, _ = self.comics
        self.tag(c1, "Civil War", 1)
        sync_tag_lists()
        reading_list = ReadingList.objects.get(name="Civil War")
        ReadingListEntry.objects.create(
            reading_list=reading_list,
            position=1,
            comic=c2,
            manual=True,
            match_tier=ReadingListMatchTier.MANUAL,
        )
        self.untag(c1)
        sync_tag_lists()
        reading_list.refresh_from_db()
        assert not ReadingListSource.objects.filter(reading_list=reading_list).exists()
        assert ReadingListEntry.objects.filter(
            reading_list=reading_list, comic=c2, manual=True
        ).exists()

    def test_case_variants_are_one_list(self) -> None:
        """Arcs that differ only in case are one list, as one arc card."""
        c1, c2, _, _ = self.comics
        self.tag(c1, "Civil War", 1)
        self.tag(c2, "civil war", 2)
        sync_tag_lists()
        assert ReadingList.objects.count() == 1
        assert self.order(ReadingList.objects.get()) == [c1.pk, c2.pk]


class VisibilityTests(ReadingListFixture):
    """Another user's personal list is invisible to every arcs endpoint."""

    @override
    def setUp(self) -> None:
        super().setUp()
        owner = User.objects.create_user(username="owner", password=_PW)
        self.owner = owner  # pyright: ignore[reportUninitializedInstanceVariable]
        self.other = User.objects.create_user(username="other", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.private = ReadingList.objects.create(name="Secret", user=owner)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.public = ReadingList.objects.create(name="Shared")  # pyright: ignore[reportUninitializedInstanceVariable]
        for position, comic in enumerate(self.comics[:2]):
            for reading_list in (self.private, self.public):
                ReadingListEntry.objects.create(
                    reading_list=reading_list,
                    position=position,
                    comic=comic,
                    match_tier=ReadingListMatchTier.MANUAL,
                )
        self.client = Client()
        self.client.force_login(self.other)

    def _params(self) -> dict:
        return {
            "filters": json.dumps({}),
            "search": "",
            "show": json.dumps(_SHOW_ALL),
            "view_mode": "cover",
        }

    def test_root_lists_only_visible_lists(self) -> None:
        """The grid of lists shows the global list, not the private one."""
        response = self.client.get("/api/v4/browse/arcs/0", self._params())
        assert response.status_code == _OK, response.content
        names = {row["name"] for row in response.json()["data"]["collections"]}
        assert names == {"Shared"}

    def test_private_list_does_not_browse(self) -> None:
        """Opening the private list by pk shows none of its comics."""
        response = self.client.get(
            f"/api/v4/browse/arcs/{self.private.pk}", self._params()
        )
        if response.status_code == _OK:
            assert not response.json()["data"].get("books")
        else:
            assert response.status_code in (302, 303, _NOT_FOUND)

    def test_public_list_browses_in_order(self) -> None:
        """The global list shows its comics in list order."""
        response = self.client.get(
            f"/api/v4/browse/arcs/{self.public.pk}", self._params()
        )
        assert response.status_code == _OK, response.content
        pks = [book["pk"] for book in response.json()["data"]["books"]]
        assert pks == [self.comics[0].pk, self.comics[1].pk]

    def test_private_list_has_no_metadata(self) -> None:
        """The metadata endpoint does not describe the private list."""
        response = self.client.get(
            f"/api/v4/browse/arcs/{self.private.pk}/metadata", self._params()
        )
        assert response.status_code != _OK

    def test_private_list_has_no_cover(self) -> None:
        """The cover route finds no comic for the private list."""
        assert _resolve_collection_comic_pk("arc", self.private.pk, self.other) is None
        assert (
            _resolve_collection_comic_pk("arc", self.public.pk, self.other)
            == self.comics[0].pk
        )

    def test_reader_offers_only_visible_lists(self) -> None:
        """The reader's reading orders name the global list only."""
        response = self.client.get(f"/api/v4/reader/comics/{self.comics[0].pk}")
        assert response.status_code == _OK, response.content
        arcs = response.json()["data"]["arcs"].get("arcs", {})
        names = {info["name"] for info in arcs.values()}
        assert names == {"Shared"}

    def test_metadata_names_only_visible_lists(self) -> None:
        """A comic's metadata lists the global list, at its position."""
        response = self.client.get(
            f"/api/v4/browse/comics/{self.comics[1].pk}/metadata", self._params()
        )
        assert response.status_code == _OK, response.content
        lists = response.json()["data"]["readingLists"]
        assert [(item["name"], item["position"], item["count"]) for item in lists] == [
            ("Shared", 2, 2)
        ]

    def test_bookmark_skips_private_list(self) -> None:
        """Marking a private list read reaches none of its comics."""
        response = self.client.patch(
            f"/api/v4/browse/arcs/{self.private.pk}/bookmark",
            data=json.dumps({"finished": True}),
            content_type="application/json",
        )
        assert response.status_code < 500  # noqa: PLR2004
        assert not Bookmark.objects.filter(user=self.other, finished=True).exists()

    def test_owner_sees_own_list(self) -> None:
        """The owner browses their own list."""
        self.client.force_login(self.owner)
        response = self.client.get(
            f"/api/v4/browse/arcs/{self.private.pk}", self._params()
        )
        assert response.status_code == _OK, response.content
        assert len(response.json()["data"]["books"]) == 2  # noqa: PLR2004

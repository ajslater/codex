"""
A live entry whose comic went is dangling: never missing, never shown.

Until the sweep drops it, every count, the missing issues, the editor,
the grid placeholders, the admin table, the metadata row and the arc
numbers written into files leave it out.
"""

import json
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client

from codex.librarian.scribe.readinglists.service import import_document
from codex.librarian.scribe.readinglists.write import arc_write
from codex.models import ReadingListEntry
from tests.test_reading_list_combine import _document, _upload
from tests.test_reading_list_live import LiveFixture

_PW: Final = "test-pw-hush-S106"
_LISTS: Final = "/api/v4/reading-lists"


def _data(response):
    body = response.json()
    return body.get("data", body)


class DanglingFixture(LiveFixture):
    """The reader's list holds Civil War; its first live row lost its comic."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.hold(self.mine, "series", self.series)
        first = (
            ReadingListEntry.objects.filter(reading_list=self.mine)
            .order_by("position")
            .first()
        )
        assert first is not None
        ReadingListEntry.objects.filter(pk=first.pk).update(comic=None)
        self.client = Client()
        self.client.force_login(self.reader)


class DanglingTests(DanglingFixture):
    """Each reader of entries leaves the dangling row out."""

    def test_the_editor_and_its_missing_filter(self) -> None:
        """Not an entry, and not a missing issue."""
        url = f"{_LISTS}/{self.mine.pk}/entries"
        entries = _data(self.client.get(url))["entries"]
        assert all(entry["comic"] for entry in entries)
        assert len(entries) == 3  # noqa: PLR2004
        assert _data(self.client.get(url, {"filter": "missing"}))["entries"] == []

    def test_the_menu_count(self) -> None:
        """Your lists count three issues."""
        lists = _data(self.client.get(f"{_LISTS}/"))["lists"]
        (mine,) = [row for row in lists if row["pk"] == self.mine.pk]
        assert mine["count"] == 3  # noqa: PLR2004

    def test_the_details_and_the_grid(self) -> None:
        """Three of three in the library, no placeholder."""
        params = {"filters": json.dumps({}), "search": ""}
        details = _data(
            self.client.get(f"/api/v4/browse/arcs/{self.mine.pk}/metadata", params)
        )["readingListDetails"]
        assert (details["inLibrary"], details["total"]) == (3, 3)
        assert details["missing"] == 0
        page = _data(
            self.client.get(
                f"/api/v4/browse/arcs/{self.mine.pk}", {**params, "page": 1}
            )
        )
        assert not page.get("missingEntries")

    def test_the_metadata_row_count(self) -> None:
        """A comic's chip says the list holds three."""
        params = {"filters": json.dumps({}), "search": ""}
        comic = self.comics[1]
        md = _data(
            self.client.get(f"/api/v4/browse/comics/{comic.pk}/metadata", params)
        )
        (row,) = [row for row in md["readingLists"] if row["pk"] == self.mine.pk]
        assert row["count"] == 3  # noqa: PLR2004

    def test_the_admin_table(self) -> None:
        """An admin's table counts three, all matched."""
        admin = User.objects.create_user(
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client.force_login(admin)
        rows = _data(self.client.get("/api/v4/admin/reading-lists"))["lists"]
        (row,) = [row for row in rows if row["pk"] == self.mine.pk]
        assert (row["total"], row["matched"]) == (3, 3)

    def test_arc_numbers_keep_no_gap_for_it(self) -> None:
        """Written into files, the three comics are numbered 1 to 3."""
        written = arc_write(self.mine)
        numbers = sorted(
            patch["arcs"][written.name]["number"] for patch in written.patches.values()
        )
        assert numbers == [1, 2, 3]


class ItemsAreNotSourcesTests(LiveFixture):
    """A collection item is not a source to name, chip or export."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.reading_list = import_document(_document(), _upload(), user=self.reader)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.hold(self.reading_list, "series", self.series)
        self.client = Client()
        self.client.force_login(self.reader)

    def test_export_names_no_item(self) -> None:
        """A folder path or a name chain never leaves in a json-cbl."""
        response = self.client.get(
            f"{_LISTS}/{self.reading_list.pk}/export", {"fmt": "json-cbl"}
        )
        body = json.loads(response.content)
        text = json.dumps(body)
        assert "collection" not in text
        assert "Marvel" not in json.dumps(
            body.get("listDetails", {}).get("sources", "")
        )

    def test_details_count_items_apart(self) -> None:
        """The details list the upload, and one item."""
        params = {"filters": json.dumps({}), "search": ""}
        details = _data(
            self.client.get(
                f"/api/v4/browse/arcs/{self.reading_list.pk}/metadata", params
            )
        )["readingListDetails"]
        assert [source["kind"] for source in details["sources"]] == ["upload"]
        assert details["items"] == 1

    def test_the_card_caption_names_only_sources(self) -> None:
        """The card reads "Upload", not "Upload + Items"."""
        params = {"filters": json.dumps({}), "search": "", "page": 1}
        page = _data(self.client.get("/api/v4/browse/arcs", params))
        (card,) = [
            row for row in page["collections"] if row["pk"] == self.reading_list.pk
        ]
        assert card["listSources"] == "Upload"

    def test_the_admin_row(self) -> None:
        """Chips for the upload; the item counted apart."""
        admin = User.objects.create_user(
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client.force_login(admin)
        rows = _data(self.client.get("/api/v4/admin/reading-lists"))["lists"]
        (row,) = [row for row in rows if row["pk"] == self.reading_list.pk]
        assert [source["kind"] for source in row["sources"]] == ["upload"]
        assert row["items"] == 1

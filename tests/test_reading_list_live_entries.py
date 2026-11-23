"""
The entries API around collection items.

A live entry is the live sync's: no person picks, hides or deletes it, and
the editor shows its item as one row. Removing a comic that is there
through its series names the series. Hand additions skip what the list
already holds and never split a block; reorders never break one.
"""

import json
from typing import Final, override

from django.test import Client

from codex.librarian.scribe.readinglists.service import import_document
from codex.models import ReadingListEntry
from tests.test_reading_list_combine import _document, _upload
from tests.test_reading_list_live import LiveFixture

_OK: Final = 200
_BAD: Final = 400
_LISTS: Final = "/api/v4/reading-lists"


def _data(response):
    body = response.json()
    return body.get("data", body)


class LiveEntriesFixture(LiveFixture):
    """The reader's list: Civil War #1 by hand, then all of Daredevil."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.client = Client()
        self.client.force_login(self.reader)
        self.daredevil, self.more = self.make_series("Daredevil")  # pyright: ignore[reportUninitializedInstanceVariable]
        ReadingListEntry.objects.create(
            reading_list=self.mine, comic=self.comics[0], manual=True
        )
        self.item = self.hold(self.mine, "series", self.daredevil)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.url = f"{_LISTS}/{self.mine.pk}"  # pyright: ignore[reportUninitializedInstanceVariable]

    def live_entry(self) -> ReadingListEntry:
        entry = ReadingListEntry.objects.filter(
            reading_list=self.mine, live_source__isnull=False
        ).first()
        assert entry is not None
        return entry

    def post(self, path: str, data):
        return self.client.post(
            f"{self.url}{path}", data=json.dumps(data), content_type="application/json"
        )


class EditorTests(LiveEntriesFixture):
    """The editor sees each item once, and its comics by their own names."""

    def test_entries_name_their_item(self) -> None:
        """Live rows carry their item; the item is one row with a count."""
        body = _data(self.client.get(f"{self.url}/entries"))
        live = [entry for entry in body["entries"] if entry["liveSource"]]
        assert [entry["seriesName"] for entry in live] == ["Daredevil", "Daredevil"]
        assert [entry["issue"] for entry in live] == ["1", "2"]
        (item,) = body["items"]
        assert item["pk"] == self.item.pk
        assert (item["collection"], item["label"]) == ("series", "Daredevil")
        assert (item["count"], item["position"]) == (2, 1)


class RefusalTests(LiveEntriesFixture):
    """A live entry is not a person's to edit."""

    def test_a_live_entry_is_not_picked_hidden_or_deleted(self) -> None:
        """Each says which item the issue is in the list through."""
        entry_url = f"{self.url}/entries/{self.live_entry().pk}"
        for response in (
            self.client.patch(
                entry_url,
                data=json.dumps({"ignored": True}),
                content_type="application/json",
            ),
            self.client.delete(entry_url),
            self.client.get(f"{entry_url}/candidates"),
        ):
            assert response.status_code == _BAD, response.content
            assert "Daredevil" in response.content.decode()
        assert not ReadingListEntry.objects.filter(
            reading_list=self.mine, ignored=True
        ).exists()

    def test_remove_names_the_series_it_cannot_remove_from(self) -> None:
        """Hand-added #1 goes; Daredevil #1 is refused, with its series."""
        c1 = self.comics[0]
        dd1 = self.more[0]
        response = self.client.patch(
            f"{self.url}/items",
            data=json.dumps({"remove": {"comics": [c1.pk, dd1.pk]}}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        body = _data(response)
        assert body["removed"] == 1
        (refused,) = body["refused"]
        assert refused["comic"] == dd1.pk
        assert refused["item"]["pk"] == self.item.pk
        assert refused["item"]["label"] == "Daredevil"
        assert dd1.pk in self.order(self.mine)
        assert c1.pk not in self.order(self.mine)


class AddTests(LiveEntriesFixture):
    """Adding by hand never repeats a comic or splits a block."""

    def test_a_held_comic_is_not_added_twice(self) -> None:
        """Civil War #1 is already in by hand."""
        response = self.post("/entries", {"comics": [self.comics[0].pk]})
        assert _data(response)["added"] == 0
        assert self.order(self.mine).count(self.comics[0].pk) == 1

    def test_a_series_comic_added_by_hand_leaves_the_block(self) -> None:
        """Held by hand now, the series no longer delivers it."""
        dd1 = self.more[0]
        assert _data(self.post("/entries", {"comics": [dd1.pk]}))["added"] == 1
        assert self.order(self.mine).count(dd1.pk) == 1
        entry = ReadingListEntry.objects.get(reading_list=self.mine, comic=dd1)
        assert entry.manual
        assert entry.live_source_id is None  # pyright: ignore[reportAttributeAccessIssue]

    def test_an_insert_inside_a_block_goes_before_it(self) -> None:
        """Position 2 is inside Daredevil, so the issue goes in at 1."""
        c1, _, c3, _ = self.comics
        self.post("/entries", {"comics": [c3.pk], "position": 2})
        assert self.order(self.mine) == [c1.pk, c3.pk, *self.pks(self.more)]


class ReorderTests(LiveEntriesFixture):
    """A reorder moves a block whole, or not at all."""

    def test_a_live_row_does_not_move_alone(self) -> None:
        """Move the item instead."""
        response = self.post(
            "/entries/reorder", {"entry": self.live_entry().pk, "position": 0}
        )
        assert response.status_code == _BAD, response.content

    def test_a_block_moves_as_a_unit(self) -> None:
        """On a hand-made list Daredevil moves to the front, whole."""
        response = self.post("/entries/reorder", {"item": self.item.pk, "position": 0})
        assert response.status_code == _OK, response.content
        assert self.order(self.mine) == [*self.pks(self.more), self.comics[0].pk]

    def test_an_imported_list_keeps_its_items_at_the_end(self) -> None:
        """Moving an issue past the block stops before it."""
        imported = import_document(_document(), _upload(), user=self.reader)
        self.hold(imported, "series", self.daredevil)
        url = f"{_LISTS}/{imported.pk}/entries/reorder"
        first = ReadingListEntry.objects.filter(reading_list=imported).order_by(
            "position"
        )[0]
        response = self.client.post(
            url,
            data=json.dumps({"entry": first.pk, "position": 99}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        order = self.order(imported)
        assert order[-2:] == self.pks(self.more)
        assert order[-3] == first.comic_id  # pyright: ignore[reportAttributeAccessIssue]


class OneStepTests(LiveEntriesFixture):
    """
    The review dialog's arrows: a position is where the issue ends up.

    One step down past Daredevil's block sends the block's last position;
    one step up from after it sends the position just before, and the
    server puts the issue before the block.
    """

    def _hand(self, comic) -> ReadingListEntry:
        return ReadingListEntry.objects.get(
            reading_list=self.mine, comic=comic, live_source__isnull=True
        )

    def test_one_step_down_past_a_block(self) -> None:
        """Civil War #1 to the block's last position: after the block."""
        c1 = self.comics[0]
        last = len(self.more)
        response = self.post(
            "/entries/reorder", {"entry": self._hand(c1).pk, "position": last}
        )
        assert response.status_code == _OK, response.content
        assert self.order(self.mine) == [*self.pks(self.more), c1.pk]

    def test_one_step_up_past_a_block(self) -> None:
        """An issue after the block, one step up: before the block."""
        c1, _, c3, _ = self.comics
        self.post("/entries", {"comics": [c3.pk]})
        assert self.order(self.mine) == [c1.pk, *self.pks(self.more), c3.pk]
        before = len(self.more)
        response = self.post(
            "/entries/reorder", {"entry": self._hand(c3).pk, "position": before}
        )
        assert response.status_code == _OK, response.content
        assert self.order(self.mine) == [c1.pk, c3.pk, *self.pks(self.more)]

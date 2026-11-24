"""
One tick in a Reading Lists menu syncs the list once (C2).

The items PATCH synced the list and its holders after each part of the
change: inside ``add_comics``, inside ``remove_comics``, and again at the
end. Now only the end does, once, in the PATCH's transaction.
"""

import json
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client

from codex.librarian.scribe.readinglists.live import add_item, reconcile_list
from codex.models import ReadingList, ReadingListEntry
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_ADD: Final = 54
_REMOVE: Final = 42


class MenuTickTests(ReadingListFixture):
    """A list that holds a volume, held by another list."""

    @override
    def setUp(self) -> None:
        super().setUp()
        user = User.objects.create_user(username="u", password=_PW)
        self.client = Client()
        self.client.force_login(user)
        self.mine = ReadingList.objects.create(name="Mine", user=user)  # pyright: ignore[reportUninitializedInstanceVariable]
        add_item(self.mine, "volumes", self.comics[0].volume_id)
        reconcile_list(self.mine)
        self.holder = ReadingList.objects.create(name="Holder", user=user)  # pyright: ignore[reportUninitializedInstanceVariable]
        add_item(self.holder, "arcs", self.mine.pk)
        reconcile_list(self.holder)
        self.url = f"/api/v4/reading-lists/{self.mine.pk}/items"  # pyright: ignore[reportUninitializedInstanceVariable]

    def _tick(self, body: dict, queries: int) -> dict:
        with self.assertNumQueries(queries):
            response = self.client.patch(
                self.url, data=json.dumps(body), content_type="application/json"
            )
        assert response.status_code == _OK, response.content
        return response.json()["data"]

    def _settled(self) -> None:
        """Check a sync from scratch finds nothing to do, here or in the holder."""
        assert not reconcile_list(self.mine)
        assert not reconcile_list(self.holder)

    def test_adding_syncs_once(self) -> None:
        comic = self.comics[1]
        assert self._tick({"add": {"comics": [comic.pk]}}, _ADD)["added"] == 1
        assert ReadingListEntry.objects.filter(
            reading_list=self.mine, comic=comic, manual=True
        ).exists()
        self._settled()

    def test_removing_syncs_once(self) -> None:
        comic = self.comics[1]
        self.client.patch(
            self.url,
            data=json.dumps({"add": {"comics": [comic.pk]}}),
            content_type="application/json",
        )
        assert self._tick({"remove": {"comics": [comic.pk]}}, _REMOVE)["removed"] == 1
        self._settled()

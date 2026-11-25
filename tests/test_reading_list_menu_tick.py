"""
One tick in a Reading Lists menu syncs the list once (C2).

The items PATCH synced the list and its holders after each part of the
change: inside ``add_comics``, inside ``remove_comics``, and again at the
end. Now only the end does, once, after the change commits: syncing the
holders inside it held the list's write lock through all of them, and a
holder's failure undid the tick. A large item is queued once the change
commits, so the librarian reads it; the rest of the change settles inline.
"""

import json
from typing import Final, override
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client

from codex.librarian.scribe.readinglists import live
from codex.librarian.scribe.readinglists.live import add_item, reconcile_list
from codex.librarian.scribe.readinglists.tasks import ReadingListLiveSyncTask
from codex.models import ReadingList, ReadingListEntry
from tests.test_reading_lists import ReadingListFixture

_QUEUE: Final = "codex.views.readinglists.items.LIBRARIAN_QUEUE"

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_ADD: Final = 55  # 1053: one query for the series with several volumes
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

    def _patch(self, body: dict, url: str = "") -> dict:
        response = self.client.patch(
            url or self.url, data=json.dumps(body), content_type="application/json"
        )
        assert response.status_code == _OK, response.content
        return response.json()["data"]

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

    def test_a_holders_failure_keeps_the_tick(self) -> None:
        """The change commits before the holders sync."""
        comic = self.comics[1]
        with (
            patch(
                "codex.views.readinglists.items.reconcile_includers",
                side_effect=RuntimeError("holder"),
            ),
            pytest.raises(RuntimeError, match="holder"),
        ):
            self._patch({"add": {"comics": [comic.pk]}})
        assert ReadingListEntry.objects.filter(
            reading_list=self.mine, comic=comic, manual=True
        ).exists()

    def test_a_large_item_is_queued_once_the_change_commits(self) -> None:
        """The librarian could otherwise read the list before the item exists."""
        publisher = self.comics[0].publisher_id
        with patch.object(live, "LIVE_INLINE_LIMIT", 2), patch(_QUEUE) as queue:
            with self.captureOnCommitCallbacks() as callbacks:  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[missing-attribute]
                assert self._patch({"add": {"publishers": [publisher]}})["queued"]
                queue.put.assert_not_called()
            assert len(callbacks) == 1
            callbacks[0]()
        (task,) = queue.put.call_args.args
        assert isinstance(task, ReadingListLiveSyncTask)
        assert task.list_pks == (self.mine.pk,)

    def test_hand_changes_settle_when_a_large_item_is_queued(self) -> None:
        """A comic the volume delivers, added by hand, shows once."""
        comic = self.comics[0]
        publisher = comic.publisher_id
        with (
            patch.object(live, "LIVE_INLINE_LIMIT", 2),
            patch(_QUEUE),
            self.captureOnCommitCallbacks(),  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[missing-attribute]
        ):
            data = self._patch(
                {"add": {"publishers": [publisher], "comics": [comic.pk]}}
            )
        assert data["queued"]
        rows = ReadingListEntry.objects.filter(reading_list=self.mine, comic=comic)
        assert list(rows.values_list("manual", flat=True)) == [True]
        assert data["count"] == len(self.comics)

    def test_several_collections_in_one_tick(self) -> None:
        """Both items land, their comics once each, and nothing is left to do."""
        other = ReadingList.objects.create(name="Other", user=self.mine.user)
        comic = self.comics[0]
        url = f"/api/v4/reading-lists/{other.pk}/items"
        data = self._patch(
            {"add": {"volumes": [comic.volume_id], "series": [comic.series_id]}},
            url,
        )
        assert (data["added"], data["queued"]) == (2, False)
        assert data["count"] == len(self.comics)
        assert not reconcile_list(other)

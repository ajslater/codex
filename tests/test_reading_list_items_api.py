"""
PATCH a list's items: issues by hand, and whole collections that stay current.

The shelves contract on lists: ``{add: {collection: [pks]}, remove:
{collection: [pks]}}``, targets the user may not see dropped silently, and
the menu GET reporting each list's direct items so the menus can toggle.
Deleting a list takes it out of every stored filter.
"""

import json
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client

from codex.librarian.scribe.readinglists import live
from codex.librarian.scribe.readinglists.tasks import ReadingListLiveSyncTask
from codex.models import ReadingList, ReadingListEntry, ReadingListSource
from codex.models.readinglist import ReadingListSourceKind
from codex.models.settings import (
    ClientChoices,
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserShow,
)
from tests.test_reading_list_live import LiveFixture

_OK: Final = 200
_BAD: Final = 400
_NOT_FOUND: Final = 404
_REDIRECT: Final = 302
_PW: Final = "test-pw-hush-S106"
_LISTS: Final = "/api/v4/reading-lists"


def _data(response):
    body = response.json()
    return body.get("data", body)


class ItemsFixture(LiveFixture):
    """The reader, signed in, with their empty list."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.client = Client()
        self.client.force_login(self.reader)

    def patch_items(self, reading_list: ReadingList, body: dict):
        return self.client.patch(
            f"{_LISTS}/{reading_list.pk}/items",
            data=json.dumps(body),
            content_type="application/json",
        )

    def items(self, reading_list: ReadingList) -> list[tuple[str, int | None]]:
        return list(
            ReadingListSource.objects.filter(
                reading_list=reading_list, kind=ReadingListSourceKind.COLLECTION
            ).values_list("collection", "target_id")
        )


class AddTests(ItemsFixture):
    """Adding issues adds issues; adding a collection keeps it current."""

    def test_issues_are_added_by_hand(self) -> None:
        """Comics become hand entries, in the order asked."""
        c1, c2, _, _ = self.comics
        response = self.patch_items(self.mine, {"add": {"comics": [c2.pk, c1.pk]}})
        assert response.status_code == _OK, response.content
        assert _data(response)["added"] == 2  # noqa: PLR2004
        assert self.order(self.mine) == [c2.pk, c1.pk]

    def test_a_series_is_an_item_that_stays_current(self) -> None:
        """The series is held whole: its comics, then a new one."""
        response = self.patch_items(self.mine, {"add": {"series": [self.series.pk]}})
        assert _data(response)["added"] == 1
        assert self.items(self.mine) == [("series", self.series.pk)]
        assert self.order(self.mine) == self.pks(self.comics)
        c5 = self.make_comic(self.series, self.volume, 5)
        live.reconcile_list(self.mine)
        assert c5.pk in self.order(self.mine)

    def test_adding_twice_adds_nothing(self) -> None:
        """Idempotent, as shelves were."""
        self.patch_items(self.mine, {"add": {"series": [self.series.pk]}})
        response = self.patch_items(self.mine, {"add": {"series": [self.series.pk]}})
        assert _data(response)["added"] == 0
        assert _data(response)["refused"] == []

    def test_a_refused_list_says_why(self) -> None:
        """A list cannot hold itself; the answer names the reason."""
        response = self.patch_items(self.mine, {"add": {"arcs": [self.mine.pk]}})
        (refused,) = _data(response)["refused"]
        assert refused["collection"] == "arcs"
        assert "itself" in refused["reason"]

    def test_unknown_collections_are_refused(self) -> None:
        """Only issues and the item collections."""
        response = self.patch_items(self.mine, {"add": {"tags": [1]}})
        assert response.status_code == _BAD, response.content

    def test_someone_elses_list_is_not_found(self) -> None:
        """Another reader's list is indistinguishable from none."""
        other = User.objects.create_user(username="other", password=_PW)
        theirs = ReadingList.objects.create(name="Theirs", user=other)
        response = self.patch_items(theirs, {"add": {"comics": [self.comics[0].pk]}})
        assert response.status_code in (_BAD, _NOT_FOUND), response.content
        assert not ReadingListEntry.objects.filter(reading_list=theirs).exists()

    def test_a_large_collection_is_synced_by_the_librarian(self) -> None:
        """Above the limit the item is saved and its sync queued."""
        with (
            patch.object(live, "LIVE_INLINE_LIMIT", 2),
            patch("codex.views.readinglists.items.LIBRARIAN_QUEUE") as queue,
        ):
            response = self.patch_items(
                self.mine, {"add": {"series": [self.series.pk]}}
            )
        assert _data(response)["queued"]
        task = queue.put.call_args.args[0]
        assert isinstance(task, ReadingListLiveSyncTask)
        assert task.list_pks == (self.mine.pk,)


class RemoveTests(ItemsFixture):
    """Removing takes issues and items out, in place."""

    def test_a_hand_added_issue_goes(self) -> None:
        """Deleted, and the rest close up."""
        c1, c2, _, _ = self.comics
        self.patch_items(self.mine, {"add": {"comics": [c1.pk, c2.pk]}})
        response = self.patch_items(self.mine, {"remove": {"comics": [c1.pk]}})
        body = _data(response)
        assert (body["removed"], body["hidden"], body["refused"]) == (1, 0, [])
        assert self.order(self.mine) == [c2.pk]

    def test_an_issue_of_a_held_series_is_refused(self) -> None:
        """It names its series, to remove instead."""
        self.patch_items(self.mine, {"add": {"series": [self.series.pk]}})
        c1 = self.comics[0]
        body = _data(self.patch_items(self.mine, {"remove": {"comics": [c1.pk]}}))
        (refused,) = body["refused"]
        assert refused["comic"] == c1.pk
        assert refused["item"]["collection"] == "series"
        assert c1.pk in self.order(self.mine)

    def test_a_series_goes_with_its_comics(self) -> None:
        """Removing the item removes what it delivered."""
        self.patch_items(self.mine, {"add": {"series": [self.series.pk]}})
        body = _data(
            self.patch_items(self.mine, {"remove": {"series": [self.series.pk]}})
        )
        assert body["removed"] == 1
        assert self.order(self.mine) == []
        assert self.items(self.mine) == []


class MenuTests(ItemsFixture):
    """The menu GET reports each list's direct items, for toggles."""

    def test_lists_report_their_direct_items(self) -> None:
        """Hand-held issues and item targets, by collection."""
        c1 = self.comics[0]
        daredevil, _ = self.make_series("Daredevil")
        self.patch_items(
            self.mine, {"add": {"comics": [c1.pk], "series": [daredevil.pk]}}
        )
        lists = _data(self.client.get(f"{_LISTS}/"))["lists"]
        (mine,) = [row for row in lists if row["pk"] == self.mine.pk]
        assert mine["items"]["comics"] == [c1.pk]
        assert mine["items"]["series"] == [daredevil.pk]
        assert mine["items"]["publishers"] == []


class DeleteTests(ItemsFixture):
    """Deleting a list takes it out of the stored filters."""

    def test_stored_filters_forget_a_deleted_list(self) -> None:
        """A saved view filtering on the list matches it no more."""
        keep = ReadingList.objects.create(name="Keep", user=self.reader)
        show, _ = SettingsBrowserShow.objects.get_or_create()
        browser = SettingsBrowser.objects.create(
            user=self.reader, client=ClientChoices.API, name="Saved", show=show
        )
        filters, _ = SettingsBrowserFilters.objects.get_or_create(browser=browser)
        filters.reading_lists = [self.mine.pk, keep.pk]
        filters.save()
        response = self.client.delete(f"{_LISTS}/{self.mine.pk}")
        assert response.status_code == _OK, response.content
        filters.refresh_from_db()
        assert filters.reading_lists == [keep.pk]


class OldRoutesTests(ItemsFixture):
    """The add and remove routes are gone: the items route replaced them."""

    def test_add_and_remove_are_gone(self) -> None:
        """Not served: codex sends an unknown path home."""
        for path in ("add", "remove"):
            response = self.client.post(
                f"{_LISTS}/{self.mine.pk}/{path}",
                data=json.dumps({}),
                content_type="application/json",
            )
            assert response.status_code in (_REDIRECT, _NOT_FOUND), path

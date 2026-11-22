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

from django.contrib.auth.models import Group, User
from django.test import Client
from django.utils import timezone

from codex.librarian.scribe.readinglists import live
from codex.librarian.scribe.readinglists.tasks import ReadingListLiveSyncTask
from codex.models import (
    Comic,
    Library,
    ReadingList,
    ReadingListEntry,
    ReadingListSource,
    Series,
    Volume,
)
from codex.models.auth import GroupAuth
from codex.models.readinglist import ReadingListSourceKind
from codex.models.settings import (
    ClientChoices,
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserShow,
)
from codex.views.readinglists.entries import add_comics
from tests.test_reading_list_live import LiveFixture
from tests.test_reading_lists import TMP_DIR

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
        # Enough to offer removing the series instead.
        assert refused["item"]["collection"] == "series"
        assert refused["item"]["targetId"] == self.series.pk
        assert refused["item"]["label"] == self.series.name
        assert c1.pk in self.order(self.mine)

    def test_removing_the_last_item_closes_the_gap(self) -> None:
        """A hand entry after the series moves up to the top."""
        _, more = self.make_series("Daredevil")
        self.patch_items(self.mine, {"add": {"series": [self.series.pk]}})
        self.patch_items(self.mine, {"add": {"comics": [more[0].pk]}})
        self.patch_items(self.mine, {"remove": {"series": [self.series.pk]}})
        positions = list(
            ReadingListEntry.objects.filter(reading_list=self.mine).values_list(
                "position", "comic_id"
            )
        )
        assert positions == [(0, more[0].pk)]

    def test_the_answer_counts_the_list(self) -> None:
        """The list's new issue count comes back, for the menus."""
        c1, c2, _, _ = self.comics
        body = _data(self.patch_items(self.mine, {"add": {"comics": [c1.pk, c2.pk]}}))
        assert body["count"] == 2  # noqa: PLR2004
        body = _data(self.patch_items(self.mine, {"remove": {"comics": [c1.pk]}}))
        assert body["count"] == 1
        body = _data(self.patch_items(self.mine, {"add": {"series": [self.series.pk]}}))
        assert body["count"] == len(self.comics)

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

    def test_the_filter_offers_your_own_lists_first(self) -> None:
        """Then the global lists, each group by name."""
        c1 = self.comics[0]
        zeta = ReadingList.objects.create(name="Zeta", user=self.reader)
        alpha = ReadingList.objects.create(name="Alpha")
        for reading_list in (self.mine, zeta, alpha):
            add_comics(reading_list, [c1.pk])
        response = self.client.get(
            f"/api/v4/browse/publishers/{self.publisher.pk}/choices/reading_lists",
            {"filters": json.dumps({})},
        )
        assert response.status_code == _OK, response.content
        names = [choice["name"] for choice in _data(response)["choices"]]
        assert names[-3:] == [self.mine.name, "Zeta", "Alpha"]


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


class VisibilityTests(ItemsFixture):
    """Ported from the shelves API: what a reader may add."""

    def test_hidden_targets_are_skipped(self) -> None:
        """A series in a library the reader cannot see adds nothing."""
        library = Library.objects.create(path=str(TMP_DIR / "hidden"))
        group = Group.objects.create(name="nobody here")
        GroupAuth.objects.create(group=group)
        library.groups.add(group)
        hidden = Series.objects.create(
            name="Hidden", imprint=self.imprint, publisher=self.publisher
        )
        volume = Volume.objects.create(
            name=1, series=hidden, imprint=self.imprint, publisher=self.publisher
        )
        comic = self.make_comic(hidden, volume, 1)
        Comic.objects.filter(pk=comic.pk).update(library=library)
        body = _data(
            self.patch_items(
                self.mine, {"add": {"comics": [comic.pk], "series": [999999]}}
            )
        )
        assert body["added"] == 0
        assert self.order(self.mine) == []

    def test_a_target_whose_file_is_missing_is_kept(self) -> None:
        """A comic pending delete may still be added, as bookmarks are."""
        c1 = self.comics[0]
        Comic.objects.filter(pk=c1.pk).update(missing_since=timezone.now())
        body = _data(self.patch_items(self.mine, {"add": {"comics": [c1.pk]}}))
        assert body["added"] == 1

    def test_anonymous_sessions_are_refused(self) -> None:
        """Only a signed-in user owns lists: to anyone else there is none."""
        self.client.logout()
        response = self.patch_items(self.mine, {"add": {"comics": [1]}})
        assert response.status_code in (401, 403, 404), response.content
        assert not ReadingListEntry.objects.filter(reading_list=self.mine).exists()

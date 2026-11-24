"""
The filter menu's list probes ask per comic, and only when there are lists (C5).

The Reading Lists and Reading List Kind availability probes each gathered
every listed comic first (``pk IN listed_comics``), five times a menu; now
each asks per comic with a correlated EXISTS that stops at the first row,
and none runs when the viewer sees no list. These tests compare the whole
availability answer with the old probes on a fixture that tells them
apart: lists of each kind, another user's list, a hidden entry, a comic on
two lists, signed in and not, with a search, and with no list at all.
"""

import json
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.models import Q
from django.test import Client

from codex.choices.admin import AdminFlagChoices
from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.models import AdminFlag, ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from codex.views.browser import choices
from codex.views.browser.choices import BrowserChoicesAvailableView
from codex.views.browser.filters.reading_lists import listed_comics
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200


def _old_listed(user, kinds=None) -> Q:
    """Test membership as the probes did before: every listed comic, first."""
    return Q(pk__in=listed_comics(user, kinds=kinds))


class ListProbeTests(ReadingListFixture):
    """A tags list, a curated list, a list of mine and one of another user."""

    @override
    def setUp(self) -> None:
        super().setUp()
        c1, c2, c3, c4 = self.comics
        self.tag(c1, "Civil War", 1)
        sync_tag_lists()
        self.user = User.objects.create_user(username="u", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]
        other = User.objects.create_user(username="other", password=_PW)
        for name, owner, rows in (
            ("Curated", None, ((c1, False), (c3, True))),
            ("Mine", self.user, ((c2, False), (c1, False))),
            ("Theirs", other, ((c4, False),)),
        ):
            reading_list = ReadingList.objects.create(name=name, user=owner)
            for position, (comic, ignored) in enumerate(rows):
                ReadingListEntry.objects.create(
                    reading_list=reading_list,
                    position=position,
                    comic=comic,
                    ignored=ignored,
                    match_tier=ReadingListMatchTier.MANUAL,
                    manual=True,
                )
        AdminFlag.objects.filter(key=AdminFlagChoices.NON_USERS.value).update(on=True)
        self.client = Client()

    def _available(self, collection: str, search: str = "") -> dict:
        params = {"filters": json.dumps({}), "search": search}
        response = self.client.get(f"/api/v4/browse/{collection}/0/choices", params)
        assert response.status_code == _OK, response.content
        return response.json()["data"]

    def _same_as_before(self, collection: str, search: str = "") -> dict:
        now = self._available(collection, search)
        with (
            patch.object(choices, "listed_q", _old_listed),
            patch.object(BrowserChoicesAvailableView, "_sees_lists", new=True),
        ):
            before = self._available(collection, search)
        assert now == before, (collection, search, now, before)
        return now

    def test_signed_in(self) -> None:
        self.client.force_login(self.user)
        for collection in ("publishers", "series", "arcs"):
            with self.subTest(collection=collection):
                available = self._same_as_before(collection)
                assert available["readingListKind"]
        assert self._available("publishers")["readingLists"]

    def test_a_new_list_reaches_the_menu(self) -> None:
        """The same request after a list changes sees it: no stale cache."""
        self.client.force_login(self.user)
        ReadingList.objects.exclude(name="Mine").delete()
        mine = ReadingList.objects.get(name="Mine")
        for comic in self.comics:
            ReadingListEntry.objects.get_or_create(
                reading_list=mine,
                comic=comic,
                defaults={"match_tier": ReadingListMatchTier.MANUAL, "manual": True},
            )
        # Every comic on one list: nothing to choose between.
        assert not self._available("publishers")["readingLists"]
        other = ReadingList.objects.create(name="Other", user=self.user)
        ReadingListEntry.objects.create(
            reading_list=other,
            comic=self.comics[0],
            match_tier=ReadingListMatchTier.MANUAL,
            manual=True,
        )
        assert self._available("publishers")["readingLists"]

    def test_signed_in_with_a_search(self) -> None:
        self.client.force_login(self.user)
        self._same_as_before("publishers", "civil")

    def test_not_signed_in(self) -> None:
        self._same_as_before("publishers")

    def test_with_no_list_at_all(self) -> None:
        self.client.force_login(self.user)
        ReadingList.objects.all().delete()
        available = self._same_as_before("publishers")
        assert not available["readingLists"]

"""
Managing reading lists in the browser: the kind toggle, the add-to-list
menu, and removing comics in place.
"""

import json
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client

from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.models import ReadingList, ReadingListEntry, ReadingListSource
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_BAD_REQUEST: Final = 400


class ManageFixture(ReadingListFixture):
    """A list from tags, an imported one, a hand-made global one, and a user's."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user(username="reader", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", password=_PW, is_staff=True
        )
        c1, c2, c3, c4 = self.comics
        self.tag(c1, "From Tags", 1)
        sync_tag_lists()
        self.tags_list = ReadingList.objects.get(name="From Tags")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imported = self._list("Imported", (c1, c2))  # pyright: ignore[reportUninitializedInstanceVariable]
        ReadingListSource.objects.create(
            reading_list=self.imported, kind=ReadingListSourceKind.UPLOAD, ref="x.cbl"
        )
        self.handmade = self._list("Hand Made", (c2, c3))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.mine = self._list("Mine", (c3, c4), user=self.user)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()
        self.client.force_login(self.user)

    @staticmethod
    def _list(name: str, comics, user=None) -> ReadingList:
        reading_list = ReadingList.objects.create(name=name, user=user)
        for position, comic in enumerate(comics):
            ReadingListEntry.objects.create(
                reading_list=reading_list,
                position=position,
                comic=comic,
                manual=True,
                match_tier=ReadingListMatchTier.MANUAL,
            )
        return reading_list

    def _root(self, kind: str) -> set[str]:
        params = {
            "filters": json.dumps({"readingListKind": kind}),
            "search": "",
        }
        response = self.client.get("/api/v4/browse/arcs/0", params)
        assert response.status_code == _OK, response.content
        return {row["name"] for row in response.json()["data"]["collections"]}


class KindToggleTests(ManageFixture):
    """All, Mine, Curated, From Tags."""

    def test_all(self) -> None:
        """Every list the viewer sees."""
        assert self._root("") == {"From Tags", "Imported", "Hand Made", "Mine"}

    def test_curated_is_not_from_tags_only(self) -> None:
        """Hand-made lists are curated too, and no longer vanish."""
        assert self._root("curated") == {"Imported", "Hand Made", "Mine"}

    def test_from_tags(self) -> None:
        """Lists whose only source is their tags."""
        assert self._root("tags") == {"From Tags"}

    def test_mine(self) -> None:
        """The viewer's own lists."""
        assert self._root("mine") == {"Mine"}

    def test_anonymous_mine_is_nothing(self) -> None:
        """A session owns no lists."""
        self.client.logout()
        assert self._root("mine") == set()


class AddToListMenuTests(ManageFixture):
    """The lists a user may add comics to, without one per story arc."""

    def _menu(self) -> set[str]:
        response = self.client.get("/api/v4/reading-lists/")
        assert response.status_code == _OK, response.content
        return {row["name"] for row in response.json()["data"]["lists"]}

    def test_a_user_gets_their_own_lists(self) -> None:
        """Only their own."""
        assert self._menu() == {"Mine"}

    def test_an_admin_gets_global_lists_not_from_tags_alone(self) -> None:
        """Imported and hand-made global lists, not the lists from tags."""
        self.client.force_login(self.admin)
        assert self._menu() == {"Imported", "Hand Made"}

"""
Shelves collect reading lists.

A shelf item of collection ``arcs`` holds a list. At the Reading Lists root
a shelf filter shows the lists on the shelf, and no other list that merely
shares an issue with one. Inside other collections it shows the lists'
comics. Shelved lists survive a backup.
"""

import json
import sqlite3
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client

from codex.models import ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from codex.models.shelf import Shelf, ShelfItem
from codex.user_data import store as store_module
from codex.user_data.dump import dump_user_data
from codex.user_data.restore import restore
from codex.user_data.store import SidecarStore, reset_store_for_tests
from tests.test_reading_lists import TMP_DIR, ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_SHOW_ALL: Final = {
    "publishers": True,
    "imprints": True,
    "series": True,
    "volumes": True,
}


class ShelvedListsFixture(ReadingListFixture):
    """A curated list and a personal list on a shelf; a third list off it."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user(username="reader", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]
        c1, c2, c3, c4 = self.comics
        self.curated = self._list("Curated", (c1, c2))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.mine = self._list("Mine", (c4,), user=self.user)  # pyright: ignore[reportUninitializedInstanceVariable]
        # Shares #2 with the curated list, and is not on the shelf.
        self.other = self._list("Other", (c2, c3))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.shelf = Shelf.objects.create(user=self.user, name="Reading")  # pyright: ignore[reportUninitializedInstanceVariable]
        for reading_list in (self.curated, self.mine):
            ShelfItem.objects.create(
                shelf=self.shelf, collection="arcs", target_id=reading_list.pk
            )
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
                match_tier=ReadingListMatchTier.MANUAL,
            )
        return reading_list

    def _params(self, *, shelf: bool = True) -> dict:
        return {
            "filters": json.dumps({"shelves": [self.shelf.pk] if shelf else []}),
            "search": "",
            "show": json.dumps(_SHOW_ALL),
            "view_mode": "cover",
        }

    def _get(self, url: str, **kwargs) -> dict:
        response = self.client.get(url, self._params(**kwargs))
        assert response.status_code == _OK, response.content
        return response.json()["data"]


class ShelfFilterOnListsTests(ShelvedListsFixture):
    """The shelf filter at the lists root and elsewhere."""

    def test_the_lists_root_shows_the_shelved_lists(self) -> None:
        """Curated and personal lists show; the list sharing an issue does not."""
        names = {
            row["name"] for row in self._get("/api/v4/browse/arcs/0")["collections"]
        }
        assert names == {"Curated", "Mine"}

    def test_without_the_filter_every_list_shows(self) -> None:
        """The filter is what narrows the root."""
        names = {
            row["name"]
            for row in self._get("/api/v4/browse/arcs/0", shelf=False)["collections"]
        }
        assert names == {"Curated", "Mine", "Other"}

    def test_inside_a_volume_the_shelved_lists_comics_show(self) -> None:
        """Another collection shows the comics of the shelved lists."""
        volume_pk = self.comics[0].volume_id
        books = self._get(f"/api/v4/browse/volumes/{volume_pk}")["books"]
        c1, c2, _, c4 = self.comics
        assert [book["pk"] for book in books] == [c1.pk, c2.pk, c4.pk]


class ShelvedListBackupTests(ShelvedListsFixture):
    """A shelved list is still on its shelf after a restore."""

    @override
    def setUp(self) -> None:
        super().setUp()
        config = TMP_DIR / "config"
        config.mkdir(parents=True, exist_ok=True)
        self.store = SidecarStore(config / "user_data.sqlite")  # pyright: ignore[reportUninitializedInstanceVariable]
        store_module._store = self.store  # noqa: SLF001

    @override
    def tearDown(self) -> None:
        self.store.close()
        reset_store_for_tests(None)
        super().tearDown()

    def test_shelf_items_round_trip(self) -> None:
        """Both lists come back, and on the shelf."""
        dump_user_data()
        self.store.connection().execute("PRAGMA wal_checkpoint(FULL)")
        snapshot = TMP_DIR / "config" / "snapshot.sqlite"
        with sqlite3.connect(snapshot) as dst:
            self.store.connection().backup(dst)
        uuids = {self.curated.uuid, self.mine.uuid}
        ReadingList.objects.all().delete()
        assert not ShelfItem.objects.exists()
        restore(sidecar_path=snapshot)
        shelved = ShelfItem.objects.filter(shelf__name="Reading", collection="arcs")
        lists = ReadingList.objects.filter(pk__in=shelved.values("target_id"))
        assert set(lists.values_list("uuid", flat=True)) == uuids

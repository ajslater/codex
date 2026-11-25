"""
The add-to-list menus list a person's own lists first (C3).

Staff also get the curated global lists. The menu ordered by owner, and
SQLite sorts a NULL owner first, so a staff member's own lists came after
every global one, against the docstring and the store.
"""

from typing import Final

from django.contrib.auth.models import User
from django.test import Client

from codex.models import ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200


class MenuOrderTests(ReadingListFixture):
    """A staff member's own list, and a curated global one."""

    def test_own_lists_come_first(self) -> None:
        staff = User.objects.create_user(
            username="staff", password=_PW, is_staff=True, is_superuser=True
        )
        for name, user in (("Alpha Event", None), ("Zed Mine", staff)):
            reading_list = ReadingList.objects.create(name=name, user=user)
            ReadingListEntry.objects.create(
                reading_list=reading_list,
                comic=self.comics[0],
                match_tier=ReadingListMatchTier.MANUAL,
                manual=True,
            )
        client = Client()
        client.force_login(staff)
        response = client.get("/api/v4/reading-lists/")
        assert response.status_code == _OK, response.content
        rows = response.json()["data"]["lists"]
        assert [(row["name"], row["personal"]) for row in rows] == [
            ("Zed Mine", True),
            ("Alpha Event", False),
        ]

"""
An admin's change to a list tells every client, as a librarian job's does.

Deleting, combining, Copy to Global, renaming and Make Private change the
lists at once, in the request. They broadcast nothing, so menus, drawers,
browsed pages and a ticked Reading Lists filter kept the lists as they were.
"""

import json
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client

from codex.librarian.notifier.tasks import (
    LIBRARY_CHANGED_TASK,
    READING_LISTS_CHANGED_TASK,
)
from codex.models import ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_ADMIN: Final = "/api/v4/admin/reading-lists"
_QUEUES: Final = (
    "codex.views.admin.reading_lists.table.LIBRARIAN_QUEUE",
    "codex.views.admin.reading_lists.review.LIBRARIAN_QUEUE",
)


class AdminChangeNotifyTests(ReadingListFixture):
    """Each change puts the lists-changed and library-changed notices out."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.admin)
        self.first = self._list("First", None)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.second = self._list("Second", None)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.mine = self._list("Mine", self.admin)  # pyright: ignore[reportUninitializedInstanceVariable]

    def _list(self, name: str, user) -> ReadingList:
        reading_list = ReadingList.objects.create(name=name, user=user)
        ReadingListEntry.objects.create(
            reading_list=reading_list,
            comic=self.comics[0],
            match_tier=ReadingListMatchTier.MANUAL,
            manual=True,
        )
        return reading_list

    def _sent(self, method: str, url: str, body: dict | None = None) -> list:
        with patch(_QUEUES[0]) as table, patch(_QUEUES[1]) as review:
            response = getattr(self.client, method)(
                url, data=json.dumps(body or {}), content_type="application/json"
            )
        assert response.status_code < 400, response.content  # noqa: PLR2004
        return [
            call.args[0]
            for queue in (table, review)
            for call in queue.put.call_args_list
        ]

    def _assert_notified(self, sent: list) -> None:
        assert READING_LISTS_CHANGED_TASK in sent, sent
        assert LIBRARY_CHANGED_TASK in sent, sent

    def test_delete(self) -> None:
        self._assert_notified(self._sent("delete", f"{_ADMIN}/{self.first.pk}"))

    def test_bulk_delete(self) -> None:
        body = {"action": "delete", "pks": [self.first.pk]}
        self._assert_notified(self._sent("post", f"{_ADMIN}/bulk", body))

    def test_copy_to_global(self) -> None:
        url = f"{_ADMIN}/{self.mine.pk}/copy_global"
        self._assert_notified(self._sent("post", url))

    def test_make_private(self) -> None:
        body = {"private": True}
        self._assert_notified(self._sent("patch", f"{_ADMIN}/{self.first.pk}", body))

    def test_combine(self) -> None:
        body = {"primary": self.first.pk, "others": [self.second.pk]}
        self._assert_notified(self._sent("post", f"{_ADMIN}/combine", body))

"""Shared fixtures for the KOReader sync tests."""

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Final, override

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.choices.admin import AdminFlagChoices
from codex.models import (
    AdminFlag,
    Bookmark,
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.models.api_key import UserApiKey
from codex.models.auth import GroupAuth
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

_TMP_DIR: Final = tmp_dir("codex.tests.koreader_sync")
OPEN_DIR: Final = _TMP_DIR / "open"
_PRIVATE_DIR: Final = _TMP_DIR / "private"
ACCEPT: Final = "application/vnd.koreader.v1+json"
PAGE_COUNT: Final = 20


def md5(value: str) -> str:
    """Return the hex MD5 KOReader sends for a password."""
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()


def set_flag(*, on: bool) -> None:
    """Turn the KOReader Sync flag on or off."""
    AdminFlag.objects.filter(key=AdminFlagChoices.KOREADER_SYNC.value).update(on=on)


class KOSyncTestCase(TestCase):
    """Fixture: an open comic, a private one and a user with a device key."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        set_flag(on=True)
        for path in (OPEN_DIR, _PRIVATE_DIR):
            path.mkdir(exist_ok=True, parents=True)
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        self.groups = (  # pyright: ignore[reportUninitializedInstanceVariable]
            publisher,
            imprint,
            series,
            Volume.objects.create(
                name="2024", series=series, imprint=imprint, publisher=publisher
            ),
        )
        self.library = Library.objects.create(path=str(OPEN_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic = self._make_comic(self.library, OPEN_DIR, "open")  # pyright: ignore[reportUninitializedInstanceVariable]

        private_library = Library.objects.create(path=str(_PRIVATE_DIR))
        readers = Group.objects.create(name="readers")
        GroupAuth.objects.create(group=readers)
        private_library.groups.add(readers)
        self.private_comic = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            private_library, _PRIVATE_DIR, "private"
        )

        self.user = User.objects.create_user(username="reader", password="x")  # noqa: S106 # pyright: ignore[reportUninitializedInstanceVariable]
        _, self.key = UserApiKey.create_for_user(self.user, "KOReader")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _make_comic(self, library, dir_path: Path, name: str, **kwargs) -> Comic:
        path = dir_path / f"{name}.cbz"
        path.write_bytes(name.encode() * 300)
        publisher, imprint, series, volume = self.groups
        return Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name=name,
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            page_count=PAGE_COUNT,
            size=42,
            **kwargs,
        )

    def _headers(self, user: str | None = None, key: str | None = None) -> dict:
        return {
            "HTTP_ACCEPT": ACCEPT,
            "HTTP_X_AUTH_USER": user if user is not None else self.user.username,
            "HTTP_X_AUTH_KEY": key if key is not None else md5(self.key),
        }

    def _push(
        self,
        document: str | None,
        progress: str | None = "5",
        percentage: float | None = 0.25,
        **headers: Any,
    ):
        body = {
            "document": document,
            "progress": progress,
            "percentage": percentage,
            "device": "Kobo",
            "device_id": "ABC",
        }
        return self.client.put(
            "/koreader/syncs/progress",
            data=json.dumps(body),
            content_type="application/json",
            **(headers or self._headers()),
        )

    def _put_raw(self, body):
        return self.client.put(
            "/koreader/syncs/progress",
            data=json.dumps(body),
            content_type="application/json",
            **self._headers(),
        )

    def _pull(self, document: str | None, **headers: Any):
        return self.client.get(
            f"/koreader/syncs/progress/{document}", **(headers or self._headers())
        )

    def _bookmarks(self) -> list[tuple[int, int | None, bool]]:
        return list(
            Bookmark.objects.order_by("comic_id").values_list(
                "comic_id", "page", "finished"
            )
        )

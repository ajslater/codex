"""Shared fixtures for the KOReader sync tests."""

import hashlib
import json
from typing import Any, Final, override

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag, Bookmark, Comic, ComicKoreaderHash, Library
from codex.models.api_key import UserApiKey
from tests.reader_fixtures import ReaderFixture
from tests.tmp_dirs import tmp_dir

ACCEPT: Final = "application/vnd.koreader.v1+json"
PAGE_COUNT: Final = 20


def md5(value: str) -> str:
    """Return the hex MD5 KOReader sends for a password."""
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()


def set_flag(*, on: bool) -> None:
    """Turn the KOReader Sync flag on or off."""
    AdminFlag.objects.filter(key=AdminFlagChoices.KOREADER_SYNC.value).update(on=on)


def binary_hash(comic: Comic) -> str | None:
    """Return the comic's stored binary (partial MD5) hash."""
    return ComicKoreaderHash.objects.get(comic_id=comic.pk).binary_hash


def name_hash(comic: Comic) -> str | None:
    """Return the comic's stored file name hash."""
    return ComicKoreaderHash.objects.get(comic_id=comic.pk).name_hash


class KOSyncTestCase(ReaderFixture):
    """Fixture: sync is on, comics are hashed and the reader holds a device key."""

    TMP_DIR = tmp_dir("codex.tests.koreader_sync")
    COMIC_PAGE_COUNT = PAGE_COUNT

    @override
    def setUp(self) -> None:
        super().setUp()
        set_flag(on=True)
        _, self.key = UserApiKey.create_for_user(self.user, "KOReader")  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def _make_comic(self, library: Library, name: str, **kwargs) -> Comic:
        """Make a comic hashed as an import with KOReader Sync on hashes it."""
        comic = super()._make_comic(library, name, **kwargs)
        ComicKoreaderHash.compute(comic.pk, comic.path, binary=True).save()
        return comic

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
        return self._put_raw(body, **headers)

    def _put_raw(self, body, **headers: Any):
        return self.client.put(
            "/koreader/syncs/progress",
            data=json.dumps(body),
            content_type="application/json",
            **(headers or self._headers()),
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

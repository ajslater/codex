"""Shared fixtures for the API key tests."""

import base64
import hashlib
import secrets
import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.choices.admin import AdminFlagChoices
from codex.choices.api_key import UNIVERSAL_KEY_NAME, ApiKeyScope
from codex.models import (
    AdminFlag,
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
from tests.api_key_factory import make_api_key
from tests.tmp_dirs import tmp_dir

PASSWORD: Final = "api-key-test-pw"  # noqa: S105
_TMP_DIR: Final = tmp_dir("codex.tests.api_keys")
OPEN_DIR: Final = _TMP_DIR / "open"
_PRIVATE_DIR: Final = _TMP_DIR / "private"
KEYS_URL: Final = "/api/v4/auth/keys"
OPDS_V2: Final = "/opds/v2.0/"
OPDS_V1: Final = "/opds/v1.2/"
KOSYNC_AUTH: Final = "/koreader/users/auth"
KOSYNC_ACCEPT: Final = "application/vnd.koreader.v1+json"
HTTP_OK: Final = 200
HTTP_CREATED: Final = 201
HTTP_NO_CONTENT: Final = 204
HTTP_FOUND: Final = 302
HTTP_BAD_REQUEST: Final = 400
HTTP_UNAUTHORIZED: Final = 401
HTTP_FORBIDDEN: Final = 403
HTTP_NOT_FOUND: Final = 404
REFUSED: Final = frozenset({HTTP_UNAUTHORIZED, HTTP_FORBIDDEN})


def basic(username: str, password: str) -> str:
    """Return a Basic ``Authorization`` header value."""
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def md5(value: str) -> str:
    """Return the hex MD5 KOReader sends for a password."""
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()


def set_flag(key: AdminFlagChoices, *, on: bool) -> None:
    """Set an admin flag and drop cached responses."""
    AdminFlag.objects.filter(key=key.value).update(on=on)
    cache.clear()


def make_universal_key(user) -> tuple[UserApiKey, str]:
    """Return a universal key shaped like a migrated DRF token, and its secret."""
    secret = secrets.token_hex(20)
    return (
        make_api_key(user, UNIVERSAL_KEY_NAME, ApiKeyScope.UNIVERSAL, secret),
        secret,
    )


class ApiKeyFixture(TestCase):
    """A visible comic, one behind a group, and a user with a device key and a universal key."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
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
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="reader", password=PASSWORD
        )
        self.universal, self.token = make_universal_key(self.user)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.api_key, self.key = UserApiKey.create_for_user(self.user, "Kobo")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.other = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="other", password=PASSWORD
        )
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
            page_count=11,
            size=42,
            **kwargs,
        )

    def _get(self, url: str, auth: str, **headers):
        return Client().get(url, HTTP_AUTHORIZATION=auth, **headers)

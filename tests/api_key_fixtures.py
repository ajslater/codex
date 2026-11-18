"""Shared fixtures for the API key tests."""

import base64
import hashlib
import secrets
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client

from codex.choices.admin import AdminFlagChoices
from codex.choices.api_key import UNIVERSAL_KEY_NAME, ApiKeyScope
from codex.models import AdminFlag
from codex.models.api_key import UserApiKey
from tests.api_key_factory import make_api_key
from tests.reader_fixtures import PASSWORD, ReaderFixture
from tests.tmp_dirs import tmp_dir

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


class ApiKeyFixture(ReaderFixture):
    """The reader also holds a device key and a universal key; another user holds none."""

    TMP_DIR = tmp_dir("codex.tests.api_keys")
    COMIC_PAGE_COUNT = 11

    @override
    def setUp(self) -> None:
        super().setUp()
        self.universal, self.token = make_universal_key(self.user)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.api_key, self.key = UserApiKey.create_for_user(self.user, "Kobo")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.other = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="other", password=PASSWORD
        )

    def _get(self, url: str, auth: str, **headers):
        return Client().get(url, HTTP_AUTHORIZATION=auth, **headers)

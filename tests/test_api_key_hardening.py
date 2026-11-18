"""
Passwords never pass through the key lookup.

Credentials also stay out of the cache and out of tracebacks.

OPDS Basic tried every password as a key first, so each password login put
``sha256(password)`` in a cachalot-cached query: a cache file whose name is
a function of the username and that fast hash. And loguru's ``diagnose``
(on by default) logs frame variables with a traceback, ``password`` and
``secret`` included.
"""

from typing import Final
from unittest.mock import patch

import pytest
from cachalot.utils import are_all_cachable
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory

from codex.authentication import ReaderKeyBasicAuthentication, get_api_key
from codex.models.api_key import generate_api_key, is_api_key_shaped
from tests.api_key_fixtures import OPDS_V2, ApiKeyFixture, basic
from tests.reader_fixtures import PASSWORD

_KEY_TABLE: Final = "codex_userapikey"


class ApiKeyShapeTestCase(ApiKeyFixture):
    """Only a key-shaped secret is looked up as a key."""

    def _basic(self, password: str):
        request = APIRequestFactory().get(
            OPDS_V2, HTTP_AUTHORIZATION=basic(self.user.username, password)
        )
        return ReaderKeyBasicAuthentication().authenticate(request)

    def test_a_password_login_never_queries_the_key_table(self) -> None:
        with CaptureQueriesContext(connection) as ctx:
            result = self._basic(PASSWORD)
        assert result is not None
        assert result[0] == self.user
        assert result[1] is None
        assert not [q for q in ctx.captured_queries if _KEY_TABLE in q["sql"]]

    def test_both_key_shapes_still_log_in(self) -> None:
        assert self._basic(self.key) == (self.user, self.api_key)
        assert self._basic(self.token) == (self.user, self.universal)

    def test_a_secret_of_another_shape_is_not_a_key(self) -> None:
        with CaptureQueriesContext(connection) as ctx:
            assert get_api_key("not a key at all", ("device",)) is None
        assert not [q for q in ctx.captured_queries if _KEY_TABLE in q["sql"]]


@pytest.mark.parametrize(
    ("secret", "shaped"),
    [
        ("rk2tcryddgsx49rr5h58", True),  # a generated key
        ("0123456789abcdef0123456789abcdef01234567", True),  # a migrated token
        ("correct horse battery staple", False),
        ("ABCDEFGHJKMNPQRSTUVW", False),  # wrong case
        ("abcdefghijkmnpqrstu0", False),  # 0 is not in the alphabet
        ("", False),
    ],
)
def test_is_api_key_shaped(secret: str, shaped: bool) -> None:  # noqa: FBT001
    """A generated key or a migrated DRF token, nothing else."""
    assert is_api_key_shaped(secret) is shaped


def test_a_generated_key_is_key_shaped() -> None:
    """Whatever the generator makes passes its own shape check."""
    assert all(is_api_key_shaped(generate_api_key()) for _ in range(100))


def test_the_key_table_is_never_cached() -> None:
    """No cache file is named after a key digest, or a password's."""
    assert not are_all_cachable({_KEY_TABLE})


def test_tracebacks_do_not_log_frame_variables() -> None:
    """``diagnose`` follows DEBUG on every main sink."""
    from loguru import logger

    from codex.settings import DEBUG
    from codex.startup.loguru import loguru_init

    with patch.object(logger, "add") as add, patch.object(logger, "remove"):
        loguru_init()
    assert add.call_args_list
    for call in add.call_args_list:
        assert call.kwargs.get("diagnose") is DEBUG, call

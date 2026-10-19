"""
CSRF trusted origins.

A reverse proxy that serves Codex under another scheme or host makes the
browser's ``Origin`` header differ from the origin Django sees, so every
unsafe API request fails the CSRF check with a 403. DRF's
``SessionAuthentication`` enforces CSRF itself, so removing
``CsrfViewMiddleware`` does not help. ``server.csrf_trusted_origins`` (or
``CODEX_CSRF_TRUSTED_ORIGINS``) is read by :func:`get_str_list` and cleaned by
:func:`normalize_csrf_trusted_origins` into Django's ``CSRF_TRUSTED_ORIGINS``.
"""

from __future__ import annotations

from contextlib import contextmanager
from http import HTTPStatus
from typing import TYPE_CHECKING, Final, override

import pytest
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from loguru import logger

from codex.settings.config import (
    _apply_env_overrides,
    get_str_list,
    normalize_csrf_trusted_origins,
)
from codex.startup import init_admin_flags

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

    from django.http import HttpResponse

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_ENV_NAME: Final = "CODEX_CSRF_TRUSTED_ORIGINS"
_KEYPATH: Final = "server.csrf_trusted_origins"
_ORIGIN_A: Final = "https://a.example.com"
_ORIGIN_B: Final = "https://b.example.com"
_PUBLIC_ORIGIN: Final = "https://comics.example.com"


@contextmanager
def _capture_logs() -> Generator[list[str]]:
    """Collect loguru WARNING+ messages emitted inside the ``with`` block."""
    records: list[str] = []
    sink_id = logger.add(records.append, level="WARNING", format="{message}")
    try:
        yield records
    finally:
        logger.remove(sink_id)


def _server(value) -> dict:
    return {"server": {"csrf_trusted_origins": value}}


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (_server([_ORIGIN_A, _ORIGIN_B]), (_ORIGIN_A, _ORIGIN_B)),
        (_server(f"{_ORIGIN_A},{_ORIGIN_B}"), (_ORIGIN_A, _ORIGIN_B)),
        (_server(f" {_ORIGIN_A} , {_ORIGIN_B} ,"), (_ORIGIN_A, _ORIGIN_B)),
        (_server(""), ()),
        (_server([]), ()),
        (_server(None), ()),
        ({"server": {}}, ()),
    ],
)
def test_get_str_list(config: Mapping, expected: tuple[str, ...]) -> None:
    """A TOML array or a comma string becomes a tuple of stripped items."""
    assert get_str_list(config, _KEYPATH) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ((f"{_ORIGIN_A}/",), (_ORIGIN_A,)),
        (("https://*.example.com",), ("https://*.example.com",)),
        ((_ORIGIN_B, _ORIGIN_A, f"{_ORIGIN_B}/"), (_ORIGIN_B, _ORIGIN_A)),
    ],
)
def test_normalize_csrf_trusted_origins(
    raw: tuple[str, ...], expected: tuple[str, ...]
) -> None:
    """Trailing slashes go, wildcards stay, duplicates collapse in order."""
    assert normalize_csrf_trusted_origins(raw) == expected


def test_normalize_drops_schemeless_origin_with_warning() -> None:
    """An entry without a scheme can never match, so it is dropped loudly."""
    with _capture_logs() as records:
        result = normalize_csrf_trusted_origins(("comics.example.com", _ORIGIN_A))
    assert result == (_ORIGIN_A,)
    assert len(records) == 1
    assert "'comics.example.com'" in records[0]
    assert "scheme://host[:port]" in records[0]


def test_env_override_reaches_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """The env var lands as the raw string and splits into origins."""
    monkeypatch.setenv(_ENV_NAME, f"{_ORIGIN_A}, {_ORIGIN_B}")
    config: dict = {}
    _apply_env_overrides(config)
    assert config["server"]["csrf_trusted_origins"] == f"{_ORIGIN_A}, {_ORIGIN_B}"
    assert get_str_list(config, _KEYPATH) == (_ORIGIN_A, _ORIGIN_B)


def test_env_override_beats_toml(monkeypatch: pytest.MonkeyPatch) -> None:
    """The env var replaces a TOML array, even when empty."""
    config = _server([_PUBLIC_ORIGIN])
    monkeypatch.setenv(_ENV_NAME, _ORIGIN_A)
    _apply_env_overrides(config)
    assert get_str_list(config, _KEYPATH) == (_ORIGIN_A,)

    monkeypatch.setenv(_ENV_NAME, "")
    _apply_env_overrides(config)
    assert get_str_list(config, _KEYPATH) == ()


class CsrfTrustedOriginsTestCase(TestCase):
    """A proxied browser passes the API's CSRF check only for a trusted origin."""

    @override
    def setUp(self) -> None:
        """Log in a CSRF-enforcing client and fetch its token."""
        init_admin_flags()
        User.objects.create_user(username="reader", password=_TEST_PASSWORD)
        self.client = Client(enforce_csrf_checks=True)
        self.client.login(username="reader", password=_TEST_PASSWORD)
        response = self.client.get("/api/v4/auth/csrf")
        self.token = response.json()["data"]["csrfToken"]  # pyright: ignore[reportUninitializedInstanceVariable]

    def _put_timezone(self) -> HttpResponse:
        # Django sees the internal http host; the browser saw the public
        # https origin, as behind a proxy that forwards neither header.
        return self.client.put(
            "/api/v4/auth/timezone",
            data={"timezone": "America/New_York"},
            content_type="application/json",
            HTTP_HOST="codex.internal",
            HTTP_ORIGIN=_PUBLIC_ORIGIN,
            HTTP_X_CSRFTOKEN=self.token,
        )

    def test_untrusted_origin_is_rejected(self) -> None:
        """Without the setting the mismatched origin fails CSRF."""
        response = self._put_timezone()
        assert response.status_code == HTTPStatus.FORBIDDEN
        body = response.content.decode()
        assert "CSRF Failed" in body
        assert "Origin checking failed" in body

    def test_trusted_origin_is_accepted(self) -> None:
        """The same request passes once its origin is trusted."""
        with override_settings(CSRF_TRUSTED_ORIGINS=[_PUBLIC_ORIGIN]):
            response = self._put_timezone()
        assert response.status_code == HTTPStatus.NO_CONTENT

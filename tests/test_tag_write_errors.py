"""Tests for tag-write error collection: the fs cache + the admin endpoint."""

from __future__ import annotations

from http import HTTPStatus
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.librarian.scribe.tagwrite_errors import (
    add_tag_write_error,
    clear_tag_write_errors,
    get_tag_write_errors,
)

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_URL: Final = "/api/v4/admin/tag-write/errors"
_CAP: Final = 100
_OVER_CAP: Final = 105


def _v4(response):
    """Unwrap the v4 ``{data, meta}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


class TagWriteErrorsCacheTestCase(TestCase):
    """The fs-cache accessors collect, dedupe, cap, and clear errors."""

    @override
    def setUp(self) -> None:
        cache.clear()

    def test_add_and_get(self) -> None:
        add_tag_write_error("/comics/a.cbz", "Read-only file system")
        errors = get_tag_write_errors()
        assert len(errors) == 1
        assert errors[0]["path"] == "/comics/a.cbz"
        assert errors[0]["error"] == "Read-only file system"
        assert errors[0]["time"]

    def test_newest_first(self) -> None:
        add_tag_write_error("/comics/a.cbz", "first")
        add_tag_write_error("/comics/b.cbz", "second")
        paths = [entry["path"] for entry in get_tag_write_errors()]
        assert paths == ["/comics/b.cbz", "/comics/a.cbz"]

    def test_dedupe_by_path_keeps_newest(self) -> None:
        add_tag_write_error("/comics/a.cbz", "old")
        add_tag_write_error("/comics/a.cbz", "new")
        errors = get_tag_write_errors()
        assert len(errors) == 1
        assert errors[0]["error"] == "new"

    def test_cap_drops_oldest(self) -> None:
        for i in range(_OVER_CAP):
            add_tag_write_error(f"/comics/{i}.cbz", "err")
        errors = get_tag_write_errors()
        assert len(errors) == _CAP
        # Newest first; the oldest beyond the cap were dropped.
        assert errors[0]["path"] == f"/comics/{_OVER_CAP - 1}.cbz"
        assert errors[-1]["path"] == f"/comics/{_OVER_CAP - _CAP}.cbz"

    def test_clear(self) -> None:
        add_tag_write_error("/comics/a.cbz", "err")
        clear_tag_write_errors()
        assert get_tag_write_errors() == []


def _make_admin() -> User:
    return User.objects.create_user(
        username="twe_admin",
        password=_TEST_PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


class TagWriteErrorsAuthTestCase(TestCase):
    """The endpoint requires admin auth."""

    @override
    def setUp(self) -> None:
        cache.clear()

    def test_anonymous_blocked(self) -> None:
        response = Client().get(_URL)
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_non_admin_blocked(self) -> None:
        User.objects.create_user(username="twe_regular", password=_TEST_PASSWORD)
        client = Client()
        client.login(username="twe_regular", password=_TEST_PASSWORD)
        response = client.get(_URL)
        assert response.status_code == HTTPStatus.FORBIDDEN


class TagWriteErrorsEndpointTestCase(TestCase):
    """Admins can read and clear the collected errors."""

    @override
    def setUp(self) -> None:
        cache.clear()
        self.client = Client()
        self.client.force_login(_make_admin())

    def test_get_returns_collected_errors(self) -> None:
        add_tag_write_error("/comics/a.cbz", "Read-only file system")
        response = self.client.get(_URL)
        assert response.status_code == HTTPStatus.OK
        errors = _v4(response)
        assert len(errors) == 1
        assert errors[0]["path"] == "/comics/a.cbz"

    def test_delete_clears_errors(self) -> None:
        add_tag_write_error("/comics/a.cbz", "err")
        with patch("codex.views.admin.tag_write_errors.LIBRARIAN_QUEUE"):
            response = self.client.delete(_URL)
        assert response.status_code == HTTPStatus.OK
        assert get_tag_write_errors() == []

"""Smoke tests for the v4 admin write paths (JSON:API resource envelope)."""

import json
import tempfile
from http import HTTPStatus
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105


def _post_jsonapi(client, url, resource_type, attributes):
    body = {"data": {"type": resource_type, "attributes": attributes}}
    return client.post(url, data=json.dumps(body), content_type="application/json")


class AdminWriteTestCase(TestCase):
    """Verify admin create endpoints accept the wrapped JSON:API body."""

    @override
    def setUp(self) -> None:
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="adminw", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def test_create_user(self) -> None:
        """POST /admin/users with a wrapped attributes block."""
        resp = _post_jsonapi(
            self.client,
            "/api/v4/admin/users",
            "users",
            {
                "username": "bar",
                "email": "",
                "password": _TEST_PASSWORD,
                "groups": [],
                "isStaff": False,
                "isActive": True,
            },
        )
        assert resp.status_code == HTTPStatus.CREATED, resp.content
        assert User.objects.filter(username="bar").exists()

    def test_create_group(self) -> None:
        """POST /admin/groups with a wrapped attributes block."""
        resp = _post_jsonapi(
            self.client,
            "/api/v4/admin/groups",
            "groups",
            {"name": "g1", "userSet": [], "librarySet": [], "exclude": False},
        )
        assert resp.status_code == HTTPStatus.CREATED, resp.content
        assert Group.objects.filter(name="g1").exists()

    def test_create_library(self) -> None:
        """POST /admin/libraries with a wrapped attributes block."""
        tmp = Path(tempfile.mkdtemp(prefix="codex.lt."))
        resp = _post_jsonapi(
            self.client,
            "/api/v4/admin/libraries",
            "libraries",
            {
                "path": str(tmp),
                "events": True,
                "poll": True,
                "pollEvery": "01:00:00",
                "groups": [],
            },
        )
        assert resp.status_code == HTTPStatus.CREATED, resp.content

    def test_change_user_password(self) -> None:
        """POST /admin/users/<pk>/password sets the password (issue #790)."""
        target = User.objects.create_user(username="pwtarget", password=_TEST_PASSWORD)
        new_password = "new-pw-hush-S106"  # noqa: S105
        resp = self.client.post(
            f"/api/v4/admin/users/{target.pk}/password",
            data=json.dumps({"password": new_password}),
            content_type="application/json",
        )
        assert resp.status_code == HTTPStatus.ACCEPTED, resp.content
        target.refresh_from_db()
        assert target.check_password(new_password)

    def test_create_user_camelcase_extra_field(self) -> None:
        """Frontend sends passwordConfirm (not on the serializer) — must not 400."""
        resp = _post_jsonapi(
            self.client,
            "/api/v4/admin/users",
            "users",
            {
                "username": "baz",
                "email": "",
                "password": _TEST_PASSWORD,
                "passwordConfirm": _TEST_PASSWORD,
                "isStaff": False,
                "isActive": True,
                "groups": [],
                "ageRatingMetron": None,
            },
        )
        assert resp.status_code == HTTPStatus.CREATED, resp.content
        assert User.objects.filter(username="baz").exists()

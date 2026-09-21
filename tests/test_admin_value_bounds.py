"""
Server-side bounds on admin values a direct API call could break.

The client's rules were the only thing standing between an admin and a
saved value that breaks the app, and a rule in a browser is not
validation. Each case here is a state reachable today with one ``curl``.
"""

import json
from http import HTTPStatus
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.choices.admin import AdminFlagChoices
from codex.choices.limits import MAX_NAME_LEN
from codex.models import AdminFlag, EmailSettings
from codex.settings.db import (
    get_browser_max_obj_per_page,
    get_custom_cover_max_upload_mb,
)
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105


def _flag_body(key: str, value: str) -> dict:
    return {"data": {"type": "flags", "id": key, "attributes": {"value": value}}}


class AdminFlagBoundsTestCase(TestCase):
    """The two integer flags stored in a shared text column."""

    @override
    def setUp(self) -> None:
        """Log in an admin client."""
        init_admin_flags()
        admin = User.objects.create_user(
            username="admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(admin)

    def _patch_flag(self, key: str, value: str):
        # The JSON:API body is sent as plain JSON, the way the client
        # does and the way the other admin write tests do.
        return self.client.patch(
            f"/api/v4/admin/flags/{key}",
            data=json.dumps(_flag_body(key, value)),
            content_type="application/json",
        )

    def _flag_value(self, key: str) -> str:
        return AdminFlag.objects.get(key=key).value

    def test_a_valid_page_size_is_accepted(self) -> None:
        """Sanity: the endpoint still works."""
        key = AdminFlagChoices.BROWSER_MAX_OBJ_PER_PAGE.value

        response = self._patch_flag(key, "50")

        assert response.status_code == HTTPStatus.OK, response.content
        assert self._flag_value(key) == "50"

    def test_a_zero_page_size_is_rejected(self) -> None:
        """
        A saved ``0`` breaks browsing entirely.

        ``get_browser_max_obj_per_page`` honours "0" -- only an empty or
        unparseable value falls back -- and ``ceil(count / 0)`` raises
        ZeroDivisionError, so every browse 500s until an admin fixes the
        flag from a UI they now cannot reach.
        """
        key = AdminFlagChoices.BROWSER_MAX_OBJ_PER_PAGE.value
        before = self._flag_value(key)

        response = self._patch_flag(key, "0")

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        assert self._flag_value(key) == before
        assert get_browser_max_obj_per_page() > 0

    def test_a_negative_upload_cap_is_rejected(self) -> None:
        """A saved ``-1`` makes every upload fail with "exceeds -1 MB limit"."""
        key = AdminFlagChoices.CUSTOM_COVER_MAX_UPLOAD_MB.value
        before = self._flag_value(key)

        response = self._patch_flag(key, "-1")

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        assert self._flag_value(key) == before
        assert get_custom_cover_max_upload_mb() > 0

    def test_an_over_large_page_size_is_rejected(self) -> None:
        """The upper bound is real too."""
        key = AdminFlagChoices.BROWSER_MAX_OBJ_PER_PAGE.value

        response = self._patch_flag(key, "999999")

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content

    def test_a_non_numeric_value_is_rejected(self) -> None:
        """It is an int flag; saying so beats falling back silently."""
        key = AdminFlagChoices.CUSTOM_COVER_MAX_UPLOAD_MB.value

        response = self._patch_flag(key, "lots")

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content

    def test_a_text_flag_is_unaffected(self) -> None:
        """The int bounds must not leak onto flags that hold strings."""
        key = AdminFlagChoices.BROWSER_DEFAULT_COLLECTION.value

        response = self._patch_flag(key, "publishers")

        assert response.status_code == HTTPStatus.OK, response.content


class EmailSettingsBoundsTestCase(TestCase):
    """SMTP port and timeout on the save path."""

    @override
    def setUp(self) -> None:
        """Log in an admin client and ensure the settings singleton."""
        init_admin_flags()
        EmailSettings.objects.get_or_create(pk=1)
        admin = User.objects.create_user(
            username="admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(admin)

    def _put(self, data: dict):
        return self.client.put(
            "/api/v4/admin/email-settings",
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_a_valid_port_is_accepted(self) -> None:
        """Sanity."""
        response = self._put({"port": 465})

        assert response.status_code == HTTPStatus.OK, response.content
        assert EmailSettings.objects.get(pk=1).port == 465  # noqa: PLR2004

    def test_port_zero_is_rejected(self) -> None:
        """
        Django derived the bounds from the SQLite integer range.

        DRF lifted those into the field, so the save path accepted 0
        and 70000 while rejecting negatives -- the practical gap the
        explicit bounds close.
        """
        before = EmailSettings.objects.get(pk=1).port

        response = self._put({"port": 0})

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        assert EmailSettings.objects.get(pk=1).port == before

    def test_an_out_of_range_port_is_rejected(self) -> None:
        """There is no port 70000."""
        response = self._put({"port": 70_000})

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content

    def test_a_zero_timeout_is_rejected(self) -> None:
        """A zero timeout is not a fast send, it is a broken one."""
        response = self._put({"timeout": 0})

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content

    def test_an_over_long_timeout_is_rejected(self) -> None:
        """Ten minutes is already generous for an SMTP handshake."""
        response = self._put({"timeout": 6000})

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content


class EmailAddressTypeTestCase(TestCase):
    """``from_address`` is the envelope sender of every outbound message."""

    @override
    def setUp(self) -> None:
        """Log in an admin client and ensure the settings singleton."""
        init_admin_flags()
        EmailSettings.objects.get_or_create(pk=1)
        admin = User.objects.create_user(
            username="admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(admin)

    def _put(self, data: dict):
        return self.client.put(
            "/api/v4/admin/email-settings",
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_a_real_address_is_accepted(self) -> None:
        """Sanity."""
        response = self._put({"from_address": "codex@example.com"})

        assert response.status_code == HTTPStatus.OK, response.content
        assert EmailSettings.objects.get(pk=1).from_address == "codex@example.com"

    def test_blank_stays_allowed(self) -> None:
        """Blank is the documented "fall back to the SMTP username" state."""
        response = self._put({"from_address": ""})

        assert response.status_code == HTTPStatus.OK, response.content

    def test_a_non_address_is_rejected(self) -> None:
        """
        It was a CharField with client-only validation.

        So anything at all could be saved as the envelope sender, and a
        malformed one fails at send time instead of at save time.
        """
        before = EmailSettings.objects.get(pk=1).from_address

        response = self._put({"from_address": "not an address"})

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        assert EmailSettings.objects.get(pk=1).from_address == before

    def test_an_over_long_host_is_rejected(self) -> None:
        """The test-send serializer carried no max_length at all."""
        response = self.client.post(
            "/api/v4/admin/email-settings/test",
            data=json.dumps(
                {"recipient": "to@example.com", "host": "h" * (MAX_NAME_LEN + 1)}
            ),
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content

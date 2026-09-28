"""PUT /api/v4/auth/timezone stores the browser timezone on the session."""

import json
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag
from codex.startup import init_admin_flags

_URL: Final = "/api/v4/auth/timezone"
_PROFILE_URL: Final = "/api/v4/auth/profile"
_SESSION_KEY: Final = "django_timezone"
_TZ: Final = "America/Los_Angeles"
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_HTTP_NO_CONTENT: Final = 204
_HTTP_BAD_REQUEST: Final = 400
_HTTP_FORBIDDEN: Final = 403


def _set_non_users(*, on: bool) -> None:
    AdminFlag.objects.filter(key=AdminFlagChoices.NON_USERS.value).update(on=on)


class TimezoneViewTests(TestCase):
    """The timezone follows the same access policy as browsing."""

    @override
    def setUp(self) -> None:
        init_admin_flags()

    @staticmethod
    def _put(client: Client, timezone: str = _TZ):
        return client.put(
            _URL,
            data=json.dumps({"timezone": timezone}),
            content_type="application/json",
        )

    def test_anonymous_with_non_users_on(self) -> None:
        """Kiosk visitors keep their timezone on the anonymous session."""
        _set_non_users(on=True)
        response = self._put(self.client)
        assert response.status_code == _HTTP_NO_CONTENT, response.content
        assert self.client.session[_SESSION_KEY] == _TZ

    def test_anonymous_with_non_users_off(self) -> None:
        """Without kiosk mode an anonymous visitor may not write a session."""
        _set_non_users(on=False)
        response = self._put(self.client)
        assert response.status_code == _HTTP_FORBIDDEN
        assert _SESSION_KEY not in self.client.session

    def test_authenticated(self) -> None:
        """A logged-in user stores it regardless of kiosk mode."""
        _set_non_users(on=False)
        user = User.objects.create_user(username="tz", password=_TEST_PASSWORD)
        self.client.force_login(user)
        response = self._put(self.client)
        assert response.status_code == _HTTP_NO_CONTENT, response.content
        assert self.client.session[_SESSION_KEY] == _TZ

    def test_unknown_timezone_rejected(self) -> None:
        """A zone ``zoneinfo`` can't load is a 400, and nothing is stored."""
        _set_non_users(on=True)
        response = self._put(self.client, "Not/AZone")
        assert response.status_code == _HTTP_BAD_REQUEST
        assert _SESSION_KEY not in self.client.session

    def test_profile_no_longer_takes_timezone(self) -> None:
        """The timezone has one write path; profile PATCH ignores it."""
        user = User.objects.create_user(username="tz", password=_TEST_PASSWORD)
        self.client.force_login(user)
        response = self.client.patch(
            _PROFILE_URL,
            data=json.dumps({"timezone": _TZ}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        assert _SESSION_KEY not in self.client.session

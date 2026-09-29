"""Shared fixtures for the admin site default settings tests."""

import json
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag, SettingsDefaults
from codex.startup import init_admin_flags, init_settings_defaults, init_timestamps

TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
URL: Final = "/api/v4/admin/settings-defaults"
REACH_URL: Final = "/api/v4/admin/settings-defaults/reach"
BROWSER_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"
READER_SETTINGS_URL: Final = "/api/v4/reader/settings"
SESSION_URL: Final = "/api/v4/session"
QUEUE: Final = "codex.views.admin.settings_defaults.LIBRARIAN_QUEUE"
SHOW_KEYS: Final = ("publishers", "imprints", "series", "volumes")
FOLDER_COLUMNS: Final = ["cover", "name", "child_count", "updated_at"]


def data_of(response) -> dict:
    """Unwrap the v4 envelope."""
    return response.json()["data"]


def put(client: Client, payload: dict, url: str = URL):
    """PUT a JSON body."""
    return client.put(url, data=json.dumps(payload), content_type="application/json")


def set_defaults(**fields) -> SettingsDefaults:
    """Write the singleton directly, bypassing the API validation."""
    row, _ = SettingsDefaults.objects.get_or_create(pk=1)
    for key, value in fields.items():
        setattr(row, key, value)
    row.save()
    return row


def set_flag(key: AdminFlagChoices, *, on: bool) -> None:
    """Turn an admin flag on or off."""
    AdminFlag.objects.filter(key=key.value).update(on=on)


class SettingsDefaultsCase(TestCase):
    """Seed the startup rows and log in a staff client."""

    @override
    def setUp(self) -> None:
        init_admin_flags()
        init_timestamps()
        init_settings_defaults()
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="defaults-admin", password=TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(self.admin)

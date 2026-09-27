"""/session carries the site default settings only to callers who may browse."""

from unittest.mock import patch

from django.test import Client

from codex.choices.admin import AdminFlagChoices
from tests.settings_defaults_helpers import (
    FOLDER_COLUMNS,
    QUEUE,
    SESSION_URL,
    SettingsDefaultsCase,
    data_of,
    put,
    set_defaults,
    set_flag,
)


class SessionDefaultsTestCase(SettingsDefaultsCase):
    """/session carries the defaults only to callers who may browse."""

    def test_authenticated_session_carries_defaults(self) -> None:
        set_defaults(bookmark="UNREAD", table_columns={"folders": FOLDER_COLUMNS})
        data = data_of(self.client.get(SESSION_URL))
        browser = data["defaults"]["browser"]
        assert browser["bookmark"] == "UNREAD"
        assert browser["tableColumns"] == {"folders": FOLDER_COLUMNS}
        assert browser["show"] == {
            "publishers": True,
            "imprints": False,
            "series": True,
            "volumes": False,
        }
        assert data["defaults"]["reader"]["fitTo"] == "W"
        assert data["defaultsRev"]

    def test_anonymous_with_non_users_on_carries_defaults(self) -> None:
        set_flag(AdminFlagChoices.NON_USERS, on=True)
        data = data_of(Client().get(SESSION_URL))
        assert "defaults" in data
        assert data["defaultsRev"]

    def test_anonymous_with_non_users_off_omits_defaults(self) -> None:
        set_flag(AdminFlagChoices.NON_USERS, on=False)
        data = data_of(Client().get(SESSION_URL))
        assert "defaults" not in data
        assert "defaultsRev" not in data

    def test_defaults_rev_changes_after_aput(self) -> None:
        before = data_of(self.client.get(SESSION_URL))["defaultsRev"]
        with patch(QUEUE):
            put(self.client, {"browser": {"viewMode": "table"}})
        after = data_of(self.client.get(SESSION_URL))
        assert after["defaultsRev"] != before
        assert after["defaults"]["browser"]["viewMode"] == "table"

"""
The API login flags fail closed, and OPDS challenges with one realm.

OPDS and Stats API Keys read a missing row as on, which is right (they
seed on), and a failed read the same way, which is not: a flag that
gates logins should fail closed, as KOReader Sync does. And OPDS binary
routes challenged Basic with DRF's realm ``api`` while the feeds said
``Codex OPDS``, so a client could prompt twice.
"""

from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from codex.authentication import ReaderKeyBasicAuthentication
from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag
from codex.settings.db import koreader_sync_enabled, opds_enabled, stats_api_enabled
from codex.startup import init_admin_flags


class ApiFlagsFailClosedTestCase(TestCase):
    """A read error is off; a missing row is the seed's value."""

    def test_a_read_error_turns_the_login_flags_off(self) -> None:
        init_admin_flags()
        with patch.object(
            AdminFlag.objects, "filter", side_effect=OperationalError("locked")
        ):
            assert opds_enabled() is False
            assert stats_api_enabled() is False
            assert koreader_sync_enabled() is False

    def test_a_missing_row_is_the_seed(self) -> None:
        AdminFlag.objects.filter(
            key__in=(AdminFlagChoices.OPDS.value, AdminFlagChoices.STATS_API.value)
        ).delete()
        assert opds_enabled() is True
        assert stats_api_enabled() is True


def test_opds_basic_challenges_with_the_feeds_realm() -> None:
    """Binary routes and feeds ask for the same realm."""
    request = APIRequestFactory().get("/opds/v2.0/")
    header = ReaderKeyBasicAuthentication().authenticate_header(request)
    assert header == 'Basic realm="Codex OPDS"'

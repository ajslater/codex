"""``patch_registration_setting`` updates the singleton, not the Django setting."""

from copy import deepcopy
from typing import Final, override

from django.conf import settings
from django.test import TestCase, override_settings
from rest_registration.settings import registration_settings

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag, EmailSettings
from codex.startup import init_admin_flags, init_timestamps
from codex.startup.registration import patch_registration_setting

_HOST: Final = "smtp.example.com"
_FROM: Final = "codex@example.com"


class PatchRegistrationSettingTests(TestCase):
    """Runtime patches reach the singleton without mutating settings in place."""

    @override
    def setUp(self) -> None:
        """Configure email + registration so patch computes the flags ON."""
        init_admin_flags()
        init_timestamps()
        AdminFlag.objects.filter(key=AdminFlagChoices.REGISTRATION.value).update(
            on=True
        )
        EmailSettings.objects.filter(pk=1).update(host=_HOST, from_address=_FROM)

    def test_updates_singleton_without_mutating_django_setting(self) -> None:
        """
        Patch leaves settings.REST_REGISTRATION untouched but updates the singleton.

        A known baseline pins ``RESET_PASSWORD_VERIFICATION_ENABLED`` OFF;
        with email configured, patch should compute it ON. An in-place
        write would flip the canonical dict — copying leaves it alone.
        ``override_settings`` also guarantees a deterministic baseline
        regardless of any earlier runtime patch in the process.
        """
        known = {
            **settings.REST_REGISTRATION,
            "RESET_PASSWORD_VERIFICATION_ENABLED": False,
        }
        with override_settings(REST_REGISTRATION=known):
            before = deepcopy(settings.REST_REGISTRATION)
            patch_registration_setting()
            assert before == settings.REST_REGISTRATION
            assert registration_settings.RESET_PASSWORD_VERIFICATION_ENABLED is True

    def test_user_settings_detached_from_django_setting(self) -> None:
        """
        After patch, the singleton's user_settings is its own dict.

        ``NestedSettings`` hands out ``settings.REST_REGISTRATION`` by
        reference; binding to it (the old behavior) would make the two
        the same object. Patching must leave them distinct.
        """
        patch_registration_setting()
        assert registration_settings.user_settings is not settings.REST_REGISTRATION

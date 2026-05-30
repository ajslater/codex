"""Shared pytest fixtures for the Codex test suite."""

import pytest
from rest_registration.settings import registration_settings


@pytest.fixture(autouse=True)
def _reset_registration_settings():  # pyright: ignore[reportUnusedFunction]
    """
    Reset rest-registration's runtime settings around every test.

    ``patch_registration_setting()`` (see
    :mod:`codex.startup.registration`) swaps a fresh override dict into
    ``registration_settings`` to flip the verification / reset-password
    flows on or off at runtime. That override lives on the in-process
    settings singleton, so it outlives a Django ``TestCase`` transaction
    rollback: a test that enables the email flow would otherwise leave it
    on for every later test, breaking the ones that assert the disabled
    default 404s.

    ``reset_user_settings`` + ``reset_attr_cache`` drop the override and
    the cached attrs so each test re-reads the configured
    ``REST_REGISTRATION`` baseline — the same reset rest-registration's
    own ``setting_changed`` handler performs for ``@override_settings``.
    """
    registration_settings.reset_user_settings()
    registration_settings.reset_attr_cache()
    yield
    registration_settings.reset_user_settings()
    registration_settings.reset_attr_cache()

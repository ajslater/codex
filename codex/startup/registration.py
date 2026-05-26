"""Patch settings at runtime."""

from rest_registration.settings import registration_settings

from codex.choices.admin import AdminFlagChoices
from codex.models.admin import AdminFlag
from codex.settings.db import email_enabled, get_email_from_address


def patch_registration_setting() -> None:
    """
    Mirror runtime state into rest-registration's settings singleton.

    ``REGISTER_FLOW_ENABLED`` tracks the ``REGISTRATION`` admin flag.
    ``REGISTER_VERIFICATION_ENABLED`` and
    ``RESET_PASSWORD_VERIFICATION_ENABLED`` both require a working
    email backend, so they follow :func:`email_enabled`, which itself
    consults the :class:`EmailSettings` singleton then the TOML/env
    fallback. ``VERIFICATION_FROM_EMAIL`` picks up the live effective
    sender so admin-saved values reach the verification emails without
    a restart.
    """
    # Technically this is a no-no, but rest-registration makes it easy.
    enr = AdminFlag.objects.only("on").get(key=AdminFlagChoices.REGISTRATION.value).on
    registration_settings.user_settings["REGISTER_FLOW_ENABLED"] = enr

    email_on = email_enabled()
    registration_settings.user_settings["REGISTER_VERIFICATION_ENABLED"] = email_on
    registration_settings.user_settings["RESET_PASSWORD_VERIFICATION_ENABLED"] = (
        email_on
    )
    registration_settings.user_settings["VERIFICATION_FROM_EMAIL"] = (
        get_email_from_address()
    )

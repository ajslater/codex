"""Patch settings at runtime."""

from django.conf import settings
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

    ``NestedSettings`` exposes ``user_settings`` *by reference* — it is
    the very ``settings.REST_REGISTRATION`` dict — so writing keys onto
    it directly would mutate the canonical Django setting in place and
    erase the configured baseline. Instead we copy that baseline, layer
    the runtime values onto the copy, swap it in as the singleton's user
    settings, and drop the attribute cache so the new values are read on
    next access. The declared ``settings.REST_REGISTRATION`` stays
    pristine.
    """
    enr = AdminFlag.objects.only("on").get(key=AdminFlagChoices.REGISTRATION.value).on
    email_on = email_enabled()
    overrides = dict(settings.REST_REGISTRATION)
    overrides["REGISTER_FLOW_ENABLED"] = enr
    overrides["REGISTER_VERIFICATION_ENABLED"] = email_on
    overrides["RESET_PASSWORD_VERIFICATION_ENABLED"] = email_on
    overrides["VERIFICATION_FROM_EMAIL"] = get_email_from_address()
    registration_settings._user_settings = overrides  # noqa: SLF001
    registration_settings.reset_attr_cache()

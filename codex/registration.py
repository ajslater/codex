"""Patch settings at runtime."""

from rest_registration.settings import registration_settings

from codex.models import AdminFlag


def patch_registration_setting():
    """Patch rest_registration setting."""
    # Technically this is a no-no, but rest-registration makes it easy.
    enr = (
        AdminFlag.objects.only("on")
        .get(key=AdminFlag.FlagChoices.REGISTRATION.value)
        .on
    )
    registration_settings.user_settings["REGISTER_FLOW_ENABLED"] = enr

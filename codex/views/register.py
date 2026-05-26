"""
Codex register view with runtime AdminFlag toggles.

Two admin flags gate the register flow:

* ``REGISTRATION`` (pre-existing) - if off, registration is disabled
  entirely (returns 404). The startup-time
  :func:`codex.startup.registration.patch_registration_setting` mirrors
  this into ``rest_registration.REGISTER_FLOW_ENABLED`` for tooling
  that introspects the setting, but the runtime check lives here so
  admin toggles via the UI take effect on the next request rather than
  the next restart.

* ``REGISTER_VERIFICATION`` (new) - when on **and** email is
  configured, new accounts are created inactive and an email
  verification link is sent. When off, new accounts are active
  immediately. Email is a hard requirement when verification is on
  (rest-registration's ``UserWithoutEmailNonverifiable`` surfaces a
  400).

The view reimplements rest-registration's register flow rather than
patching ``registration_settings`` at request time - that singleton
caches attribute values and isn't safely mutable under load.
"""

from typing import override

from django.db import transaction
from django.http import Http404
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_registration import signals
from rest_registration.api.views.register import RegisterView as _RegisterView
from rest_registration.exceptions import UserWithoutEmailNonverifiable
from rest_registration.settings import registration_settings
from rest_registration.utils.users import (
    get_user_email_field_name,
    get_user_setting,
)

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag
from codex.settings.db import email_enabled


def _admin_flag_on(key: str) -> bool:
    return AdminFlag.objects.filter(key=key, on=True).exists()


class RegisterView(_RegisterView):
    """Codex register view with runtime AdminFlag toggles."""

    @override
    def post(self, request: Request) -> Response:
        """Register a new user, honoring ``REGISTRATION`` + ``REGISTER_VERIFICATION``."""
        if not _admin_flag_on(AdminFlagChoices.REGISTRATION.value):
            raise Http404

        verification_required = email_enabled() and _admin_flag_on(
            AdminFlagChoices.REGISTER_VERIFICATION.value
        )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        save_kwargs = {}
        if verification_required:
            verification_flag_field = get_user_setting("VERIFICATION_FLAG_FIELD")
            save_kwargs[verification_flag_field] = False
            email_field_name = get_user_email_field_name()
            if not serializer.validated_data.get(email_field_name):
                raise UserWithoutEmailNonverifiable

        with transaction.atomic():
            user = serializer.save(**save_kwargs)
            if verification_required:
                email_sender = registration_settings.REGISTER_VERIFICATION_EMAIL_SENDER
                email_sender(request, user)

        signals.user_registered.send(sender=None, user=user, request=request)
        output_serializer_class = registration_settings.REGISTER_OUTPUT_SERIALIZER_CLASS
        output_serializer = output_serializer_class(
            instance=user,
            context={"request": request},
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

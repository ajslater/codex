"""Codex Auth Serializers."""

from typing import override

from django.conf import settings
from rest_framework.fields import BooleanField, CharField
from rest_framework.serializers import (
    Serializer,
    SerializerMetaclass,
)
from rest_registration.api.serializers import DefaultUserProfileSerializer

from codex.serializers.fields.auth import TimezoneField


class CodexProfileSerializer(DefaultUserProfileSerializer):
    """
    Profile serializer for self-service edits of username + email.

    ``DefaultUserProfileSerializer`` hard-codes the email field as
    read-only on the assumption that callers go through
    rest-registration's register-email -> verify-email handshake. Codex
    doesn't run that flow; users set their own email directly via the
    profile dialog, so this subclass flips ``email`` back to writable.

    When ``AUTH_REMOTE_USER`` is on, identity is owned by the upstream
    proxy; letting a user rename themselves in Codex would desync them
    from the IdP and lock them out. ``username`` stays visible so the
    UI can render it but becomes read-only - DRF's standard read-only
    behaviour drops writes silently rather than 400-ing, which is the
    right "managed elsewhere" semantics behind the disabled UI control.
    """

    @override
    def get_fields(self):
        """Make email writable; lock username under remote-user auth."""
        fields = super().get_fields()
        email = fields.get("email")
        if email is not None:
            email.read_only = False
            email.required = False
            # ``allow_blank`` lives on the ``CharField`` subclass; the
            # ModelSerializer auto-generates a ``CharField`` for the
            # User.email column, so this attribute is present in
            # practice. Set via setattr to avoid the static-checker
            # walking the parent ``Field`` type and complaining.
            if hasattr(email, "allow_blank"):
                setattr(email, "allow_blank", True)  # noqa: B010
        if settings.AUTH_REMOTE_USER and "username" in fields:
            fields["username"].read_only = True
        return fields


class TimezoneSerializerMixin(metaclass=SerializerMetaclass):
    """Serialize Timezone submission from front end."""

    timezone = TimezoneField(write_only=True)


class TimezoneSerializer(TimezoneSerializerMixin, Serializer):
    """Serialize Timezone submission from front end."""


class AuthAdminFlagsSerializer(Serializer):
    """Admin flags related to auth."""

    banner_text = CharField(read_only=True)
    lazy_import_metadata = BooleanField(read_only=True)
    non_users = BooleanField(read_only=True)
    registration = BooleanField(read_only=True)
    register_verification = BooleanField(read_only=True)
    # Settings-derived capabilities (not DB-backed AdminFlags) - exposed
    # alongside the flag rows so the frontend gets a single payload.
    email_enabled = BooleanField(read_only=True)
    remote_user_enabled = BooleanField(read_only=True)

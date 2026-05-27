"""Codex Auth Serializers."""

from typing import override

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from rest_framework.fields import BooleanField, CharField, EmailField, IntegerField
from rest_framework.serializers import (
    Serializer,
    SerializerMetaclass,
)
from rest_registration.api.serializers import DefaultUserProfileSerializer

from codex.serializers.fields.auth import TimezoneField
from codex.serializers.versions import VersionsSerializer


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


class PermissionsSerializer(Serializer):
    """User capability flags derived from the request.user."""

    is_staff = BooleanField(read_only=True)
    is_superuser = BooleanField(read_only=True)


class AdminFlagsSerializer(Serializer):
    """Admin flags + capability flags relevant to auth/registration."""

    banner_text = CharField(read_only=True, allow_blank=True)
    lazy_import_metadata = BooleanField(read_only=True)
    non_users = BooleanField(read_only=True)
    registration = BooleanField(read_only=True)
    register_verification = BooleanField(read_only=True)
    email_enabled = BooleanField(read_only=True)
    remote_user_enabled = BooleanField(read_only=True)


class UserSerializer(Serializer):
    """User shape served by ``/session`` and ``/auth/profile``."""

    id = IntegerField(read_only=True)
    username = CharField(read_only=True)
    email = EmailField(read_only=True, allow_blank=True)
    is_staff = BooleanField(read_only=True)
    is_superuser = BooleanField(read_only=True)


class SessionSerializer(Serializer):
    """
    Composite session payload: user + adminFlags + permissions + version.

    ``opds-urls`` deliberately stays on its own lazy endpoint
    (``GET /api/v4/opds-urls``) — those URLs are rarely opened, so
    paying for the reverse-resolve on every session boot would be
    waste. ``version`` ships here because the SPA chrome reads
    ``installed`` immediately and the update-check fields ride along
    for free off the same Timestamp row.
    """

    user = UserSerializer(allow_null=True)
    admin_flags = AdminFlagsSerializer()
    permissions = PermissionsSerializer()
    version = VersionsSerializer()


class ProfileUpdateSerializer(Serializer):
    """
    Writable subset of the user profile.

    ``username`` is read-only when ``AUTH_REMOTE_USER`` owns identity.
    Empty strings on ``email`` mean "clear it"; the
    rest-registration-backed profile view accepts that semantics.
    """

    username = CharField(required=False, allow_blank=False)
    email = EmailField(required=False, allow_blank=True)
    timezone = TimezoneField(required=False, write_only=True)

    @override
    def get_fields(self):
        """Lock username under remote-user auth (matches v3 profile semantics)."""
        fields = super().get_fields()
        if settings.AUTH_REMOTE_USER and "username" in fields:
            fields["username"].read_only = True
        return fields

    def validate_username(self, value: str) -> str:
        """
        Reject a rename onto an existing username up front.

        The DB has a UNIQUE constraint on ``username`` so a colliding
        save would raise ``IntegrityError``. Catch it here as a clean
        400 with field-scoped error rather than letting the constraint
        surface as a 500.
        """
        request = self.context.get("request") if self.context else None
        current_user = getattr(request, "user", None) if request else None
        user_model = get_user_model()
        username_field = getattr(user_model, "USERNAME_FIELD", "username")
        qs = user_model.objects.filter(**{username_field: value})
        if current_user and getattr(current_user, "pk", None):
            qs = qs.exclude(pk=current_user.pk)
        if qs.exists():
            msg = "A user with that username already exists."
            raise ValidationError(msg)
        return value

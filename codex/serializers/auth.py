"""Codex Auth Serializers."""

from typing import override

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from rest_framework.fields import (
    BooleanField,
    CharField,
    DictField,
    EmailField,
    IntegerField,
    ListField,
)
from rest_framework.serializers import Serializer
from rest_registration.api.serializers import DefaultUserProfileSerializer

from codex.oidc import user_is_oidc_managed
from codex.serializers.fields.auth import TimezoneField
from codex.serializers.versions import VersionsSerializer


def _username_locked(serializer: Serializer) -> bool:
    """
    Return whether an external identity manages the request user's username.

    Global when ``AUTH_REMOTE_USER`` owns identity; per-user when the
    account is linked to an OIDC identity provider. Renaming in either
    case would desync the user from the IdP and lock them out.
    """
    if settings.AUTH_REMOTE_USER:
        return True
    request = serializer.context.get("request") if serializer.context else None
    return user_is_oidc_managed(getattr(request, "user", None))


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
        """Make email writable; lock username under external identity."""
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
        if "username" in fields and _username_locked(self):
            fields["username"].read_only = True
        return fields


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
    oidc_enabled = BooleanField(read_only=True)
    oidc_provider_name = CharField(read_only=True, allow_blank=True)
    oidc_login_url = CharField(read_only=True, allow_blank=True)
    oidc_logout_url = CharField(read_only=True, allow_blank=True)


class UserSerializer(Serializer):
    """User shape served by ``/session`` and ``/auth/profile``."""

    id = IntegerField(read_only=True)
    username = CharField(read_only=True)
    email = EmailField(read_only=True, allow_blank=True)
    is_staff = BooleanField(read_only=True)
    is_superuser = BooleanField(read_only=True)


class SessionBrowserDefaultsSerializer(Serializer):
    """Site default browser settings. Closed vocabulary only."""

    top_collection = CharField(read_only=True)
    show = DictField(child=BooleanField(), read_only=True)
    order_by = CharField(read_only=True, allow_blank=True)
    order_reverse = BooleanField(read_only=True)
    view_mode = CharField(read_only=True)
    twenty_four_hour_time = BooleanField(read_only=True)
    always_show_filename = BooleanField(read_only=True)
    bookmark = CharField(read_only=True, allow_blank=True)
    table_columns = DictField(child=ListField(child=CharField()), read_only=True)


class SessionReaderDefaultsSerializer(Serializer):
    """Site default global reader settings."""

    fit_to = CharField(read_only=True)
    reading_direction = CharField(read_only=True)
    two_pages = BooleanField(read_only=True)
    page_transition = BooleanField(read_only=True)
    cache_book = BooleanField(read_only=True)
    finish_on_last_page = BooleanField(read_only=True)
    read_rtl_in_reverse = BooleanField(read_only=True)


class SessionDefaultsSerializer(Serializer):
    """Site default settings that seed a new session's first paint."""

    browser = SessionBrowserDefaultsSerializer(read_only=True)
    reader = SessionReaderDefaultsSerializer(read_only=True)


class SessionSerializer(Serializer):
    """
    Composite session payload: user + adminFlags + permissions + version.

    ``opds-urls`` deliberately stays on its own lazy endpoint
    (``GET /api/v4/opds-urls``) — those URLs are rarely opened, so
    paying for the reverse-resolve on every session boot would be
    waste. ``version`` ships here because the SPA chrome reads
    ``installed`` immediately and the update-check fields ride along
    for free off the same Timestamp row.

    ``defaults`` and ``defaults_rev`` ship only to callers who may browse:
    authenticated users, or anyone while Non-Users is on. Both are omitted
    otherwise, so an anonymous caller facing the login screen learns
    nothing about the site's browser settings.
    """

    user = UserSerializer(allow_null=True)
    admin_flags = AdminFlagsSerializer()
    permissions = PermissionsSerializer()
    version = VersionsSerializer()
    defaults = SessionDefaultsSerializer(read_only=True)
    defaults_rev = CharField(read_only=True, allow_blank=True)


class TimezoneSerializer(Serializer):
    """The browser's IANA timezone, stored on the session."""

    timezone = TimezoneField(write_only=True)


class ProfileUpdateSerializer(Serializer):
    """
    Writable subset of the user profile.

    ``username`` is read-only when an external identity (remote-user
    proxy or a linked OIDC provider) owns it. Empty strings on ``email``
    mean "clear it"; the rest-registration-backed profile view accepts
    that semantics.
    """

    username = CharField(required=False, allow_blank=False)
    email = EmailField(required=False, allow_blank=True)

    @override
    def get_fields(self):
        """Lock username under external identity (matches v3 profile semantics)."""
        fields = super().get_fields()
        if "username" in fields and _username_locked(self):
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

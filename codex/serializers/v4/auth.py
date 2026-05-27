"""
API v4 session, profile, and admin-flag serializers.

The v4 ``/session`` endpoint composites what v3 split across
``/auth/profile`` + ``/auth/flags`` into a single payload so the SPA
boots with one request. See ``tasks/api-v4.md`` Phase 2.
"""

from typing import override

from django.conf import settings
from rest_framework.fields import (
    BooleanField,
    CharField,
    EmailField,
    IntegerField,
)
from rest_framework.serializers import Serializer

from codex.serializers.fields.auth import TimezoneField


class V4PermissionsSerializer(Serializer):
    """User capability flags derived from the request.user."""

    is_staff = BooleanField(read_only=True)
    is_superuser = BooleanField(read_only=True)


class V4AdminFlagsSerializer(Serializer):
    """Admin flags + capability flags relevant to auth/registration."""

    banner_text = CharField(read_only=True, allow_blank=True)
    lazy_import_metadata = BooleanField(read_only=True)
    non_users = BooleanField(read_only=True)
    registration = BooleanField(read_only=True)
    register_verification = BooleanField(read_only=True)
    email_enabled = BooleanField(read_only=True)
    remote_user_enabled = BooleanField(read_only=True)


class V4UserSerializer(Serializer):
    """User shape served by ``/session`` and ``/auth/profile``."""

    id = IntegerField(read_only=True)
    username = CharField(read_only=True)
    email = EmailField(read_only=True, allow_blank=True)
    is_staff = BooleanField(read_only=True)
    is_superuser = BooleanField(read_only=True)


class V4SessionSerializer(Serializer):
    """Composite session payload: user + adminFlags + permissions."""

    user = V4UserSerializer(allow_null=True)
    admin_flags = V4AdminFlagsSerializer()
    permissions = V4PermissionsSerializer()


class V4ProfileUpdateSerializer(Serializer):
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

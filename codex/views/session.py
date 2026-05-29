"""
Composite session bootstrap endpoint.

``GET /api/v4/session`` returns ``{user, adminFlags, permissions,
version}`` in a single request so the SPA boots without the two-call
``/auth/profile`` + ``/auth/flags`` handshake that v3 used.
``opds-urls`` is intentionally *not* bundled — those URLs are rarely
opened, so they stay on their own lazy ``/api/v4/opds-urls`` endpoint.
"""

from typing import override

from django.conf import settings
from rest_framework.response import Response

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag
from codex.serializers.auth import SessionSerializer
from codex.settings.db import email_enabled
from codex.views.auth import AuthGenericAPIView, user_payload
from codex.views.version import version_payload

_ADMIN_FLAG_KEYS = (
    AdminFlagChoices.BANNER_TEXT.value,
    AdminFlagChoices.LAZY_IMPORT_METADATA.value,
    AdminFlagChoices.NON_USERS.value,
    AdminFlagChoices.REGISTRATION.value,
    AdminFlagChoices.REGISTER_VERIFICATION.value,
)


class SessionView(AuthGenericAPIView):
    """``GET /api/v4/session`` — current user + admin flags + permissions."""

    serializer_class = SessionSerializer

    @staticmethod
    def _admin_flags() -> dict:
        """Build the auth-relevant admin flags + settings-derived capabilities."""
        flags: dict = {}
        rows = AdminFlag.objects.filter(key__in=_ADMIN_FLAG_KEYS).only(
            "key", "on", "value"
        )
        for row in rows:
            name = AdminFlagChoices(row.key).name.lower()
            flags[name] = (
                row.value if row.key == AdminFlagChoices.BANNER_TEXT.value else row.on
            )
        flags["email_enabled"] = email_enabled()
        flags["remote_user_enabled"] = bool(settings.AUTH_REMOTE_USER)
        return flags

    @override
    def get_object(self) -> dict:
        """Build the composite session payload."""
        user_data = user_payload(self.request.user)
        return {
            "user": user_data,
            "admin_flags": self._admin_flags(),
            "permissions": {
                "is_staff": bool(user_data and user_data["is_staff"]),
                "is_superuser": bool(user_data and user_data["is_superuser"]),
            },
            "version": version_payload(),
        }

    def get(self, *args, **kwargs) -> Response:
        """GET /api/v4/session."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

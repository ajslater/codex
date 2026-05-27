"""
GET /api/v4/session — composite bootstrap response.

Replaces v3's two-call ``/auth/profile`` + ``/auth/flags`` boot with a
single request that returns ``{user, adminFlags, permissions}``. See
``tasks/api-v4.md`` Phase 2.
"""

from typing import override

from django.conf import settings
from rest_framework.response import Response

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag
from codex.serializers.v4.auth import V4SessionSerializer
from codex.settings.db import email_enabled
from codex.views.v4.common import V4GenericAPIView, envelope

_ADMIN_FLAG_KEYS = (
    AdminFlagChoices.BANNER_TEXT.value,
    AdminFlagChoices.LAZY_IMPORT_METADATA.value,
    AdminFlagChoices.NON_USERS.value,
    AdminFlagChoices.REGISTRATION.value,
    AdminFlagChoices.REGISTER_VERIFICATION.value,
)


class V4SessionView(V4GenericAPIView):
    """``GET /api/v4/session`` — current user + admin flags + permissions."""

    serializer_class = V4SessionSerializer

    @staticmethod
    def _admin_flags() -> dict:
        """Mirror ``AdminFlagsView`` payload; settings-derived flags inlined."""
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

    @staticmethod
    def _user_payload(user) -> dict | None:
        """Return the user dict, or None for anonymous sessions."""
        if not user or not getattr(user, "is_authenticated", False):
            return None
        return {
            "id": user.pk,
            "username": user.get_username(),
            "email": getattr(user, "email", "") or "",
            "is_staff": bool(getattr(user, "is_staff", False)),
            "is_superuser": bool(getattr(user, "is_superuser", False)),
        }

    @override
    def get_object(self) -> dict:
        """Build the composite session payload."""
        user_payload = self._user_payload(self.request.user)
        return {
            "user": user_payload,
            "admin_flags": self._admin_flags(),
            "permissions": {
                "is_staff": bool(user_payload and user_payload["is_staff"]),
                "is_superuser": bool(user_payload and user_payload["is_superuser"]),
            },
        }

    def get(self, *args, **kwargs) -> Response:
        """GET /api/v4/session."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(envelope(serializer.data))

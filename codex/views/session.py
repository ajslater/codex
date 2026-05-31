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
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag
from codex.serializers.auth import SessionSerializer
from codex.settings.db import email_enabled
from codex.views.auth import AuthGenericAPIView, user_payload
from codex.views.version import version_payload

# Auth-relevant flags every visitor needs to render the logged-out
# shell: whether to offer registration (and, in register mode, the
# email-verification notice), whether to permit kiosk (non-user)
# browsing, and the global banner. ``email_enabled`` (computed in
# ``_admin_flags``) joins this public set because the logged-out login
# dialog shows the reset-password link when it's on.
_PUBLIC_ADMIN_FLAG_KEYS = (
    AdminFlagChoices.BANNER_TEXT.value,
    AdminFlagChoices.NON_USERS.value,
    AdminFlagChoices.REGISTRATION.value,
    AdminFlagChoices.REGISTER_VERIFICATION.value,
)
# Behaviour flags only the authenticated UI reads: lazy import lives on
# book cards behind the browser, and ``remote_user_enabled`` (computed
# in ``_admin_flags``) only drives the profile dialog. Withheld from
# anonymous callers now that ``/session`` is public, so an unauthed boot
# discloses nothing beyond what the logged-out screen actually needs.
_PRIVATE_ADMIN_FLAG_KEYS = (AdminFlagChoices.LAZY_IMPORT_METADATA.value,)


class SessionView(AuthGenericAPIView):
    """``GET /api/v4/session`` — current user + admin flags + permissions."""

    # The SPA boots every visitor through this endpoint, logged in or
    # not: the logged-out shell needs ``registration`` / ``non_users``
    # to decide whether to show login, kiosk browsing, or registration.
    # Gating it behind ``IsAuthenticatedOrEnabledNonUsers`` deadlocked
    # the anonymous + non-users-off case — the flags never arrived, so
    # ``isAuthChecked`` stayed false and the browser spun forever. The
    # payload is anonymous-safe by construction (``user`` is null,
    # ``permissions`` all-false) and ``_admin_flags`` withholds the
    # authenticated-only behaviour flags.
    permission_classes = (AllowAny,)
    serializer_class = SessionSerializer

    @staticmethod
    def _admin_flags(*, authenticated: bool) -> dict:
        """
        Build the auth-relevant admin flags + settings-derived capabilities.

        Anonymous callers receive only the public subset (plus
        ``email_enabled``) — exactly what the logged-out shell renders.
        Authenticated sessions additionally get the librarian/remote-user
        behaviour flags. Keys absent from the dict are dropped by the
        serializer (its fields are ``read_only`` ⇒ optional), so the
        frontend simply sees them as ``undefined``.
        """
        keys = _PUBLIC_ADMIN_FLAG_KEYS
        if authenticated:
            keys = (*keys, *_PRIVATE_ADMIN_FLAG_KEYS)
        flags: dict = {}
        rows = AdminFlag.objects.filter(key__in=keys).only("key", "on", "value")
        for row in rows:
            name = AdminFlagChoices(row.key).name.lower()
            flags[name] = (
                row.value if row.key == AdminFlagChoices.BANNER_TEXT.value else row.on
            )
        # Public: the logged-out login dialog shows the reset-password
        # link when email is configured.
        flags["email_enabled"] = email_enabled()
        # Private: only the authenticated profile dialog reads this.
        if authenticated:
            flags["remote_user_enabled"] = bool(settings.AUTH_REMOTE_USER)
        return flags

    @override
    def get_object(self) -> dict:
        """Build the composite session payload."""
        user_data = user_payload(self.request.user)
        return {
            "user": user_data,
            "admin_flags": self._admin_flags(authenticated=user_data is not None),
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

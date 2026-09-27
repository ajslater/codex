"""
Composite session bootstrap endpoint.

``GET /api/v4/session`` returns ``{user, adminFlags, permissions,
version}`` (plus ``defaults`` and ``defaultsRev`` for callers who may
browse) in a single request so the SPA boots without the two-call
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
from codex.oidc import oidc_logout_url
from codex.serializers.auth import SessionSerializer
from codex.settings import GRANIAN_URL_PATH_PREFIX
from codex.settings.db import (
    email_enabled,
    get_browser_defaults,
    get_oidc_settings,
    get_reader_defaults,
    get_settings_defaults,
    oidc_enabled,
)
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

    def _admin_flags(self, *, authenticated: bool) -> dict:
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
        # Public, unlike remote_user_enabled: the logged-out shell must
        # render the "Login with <provider>" button.
        oidc_row = get_oidc_settings()
        oidc_on = oidc_enabled(oidc_row)
        flags["oidc_enabled"] = oidc_on
        if oidc_on and oidc_row:
            flags["oidc_provider_name"] = oidc_row.provider_name or "SSO"
            flags["oidc_login_url"] = (
                f"{GRANIAN_URL_PATH_PREFIX}/api/v4/auth/oidc/login"
            )
        # Private: only the authenticated profile dialog reads this.
        if authenticated:
            flags["remote_user_enabled"] = bool(settings.AUTH_REMOTE_USER)
            # Computed while still authenticated because the frontend
            # navigates here only after the local logout POST succeeds.
            if logout_url := oidc_logout_url(self.request):
                flags["oidc_logout_url"] = logout_url
        return flags

    @staticmethod
    def _add_defaults(payload: dict) -> None:
        """
        Add the site default settings and their revision.

        ``defaults_rev`` is the singleton's ``updated_at``, so every admin
        Save changes it and open tabs can tell a real change from a refetch.
        """
        payload["defaults"] = {
            "browser": get_browser_defaults(),
            "reader": get_reader_defaults(),
        }
        row = get_settings_defaults()
        payload["defaults_rev"] = row.updated_at.isoformat() if row else ""

    @override
    def get_object(self) -> dict:
        """Build the composite session payload."""
        user_data = user_payload(self.request.user)
        flags = self._admin_flags(authenticated=user_data is not None)
        payload = {
            "user": user_data,
            "admin_flags": flags,
            "permissions": {
                "is_staff": bool(user_data and user_data["is_staff"]),
                "is_superuser": bool(user_data and user_data["is_superuser"]),
            },
            "version": version_payload(),
        }
        # Only a caller who may browse needs the defaults to seed its first
        # paint; an anonymous caller with Non-Users off sees a login screen.
        if user_data is not None or flags.get("non_users"):
            self._add_defaults(payload)
        return payload

    def get(self, *args, **kwargs) -> Response:
        """GET /api/v4/session."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

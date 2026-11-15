"""Custom Authentication classes."""

import hashlib
import hmac
from typing import override

from django.contrib.auth.middleware import RemoteUserMiddleware
from rest_framework.authentication import (
    BaseAuthentication,
    RemoteUserAuthentication,
    TokenAuthentication,
)
from rest_framework.exceptions import AuthenticationFailed


class BearerTokenAuthentication(TokenAuthentication):
    """Bearer Token Authentication."""

    keyword = "Bearer"


class HttpRemoteUserAuthentication(RemoteUserAuthentication):
    """
    Http Remote User Authentication for DRF.

    DRF's stock ``RemoteUserAuthentication`` reads ``REMOTE_USER``,
    which is only populated by on-machine WSGI/ASGI socket magic.
    Behind a reverse proxy that forwards a ``Remote-User`` header,
    the value arrives under ``HTTP_REMOTE_USER`` instead. DRF needs
    its own auth class for that path because ``SessionAuthentication``
    enforces CSRF on unsafe methods, which breaks proxy-authenticated
    API clients that do not carry a CSRF token.
    """

    header = "HTTP_REMOTE_USER"


class HttpRemoteUserMiddleware(RemoteUserMiddleware):
    """
    Http Remote User Backend.

    Regular REMOTE_USER can only be set by on machine wgsi socket magic.
    """

    header = "HTTP_REMOTE_USER"


class KOSyncAuthentication(BaseAuthentication):
    """
    KOReader kosync authentication.

    KOReader sends ``x-auth-user`` and ``x-auth-key``, the lowercase hex
    MD5 of the password typed on the device. Codex uses the user's API
    bearer token as that password, so the key is compared with the MD5 of
    the user's DRF ``Token``. Only the KOReader views use this class, and
    they use nothing else: no session, no anonymous access.
    """

    @staticmethod
    def _token_key_md5(token_key: str) -> str:
        return hashlib.md5(token_key.encode(), usedforsecurity=False).hexdigest()

    @override
    def authenticate(self, request):
        """Authenticate the KOReader auth headers against the user's token."""
        # Imported here: HttpRemoteUserMiddleware in this module loads
        # with the middleware stack, and models must wait for app loading.
        from rest_framework.authtoken.models import Token

        username = request.headers.get("x-auth-user")
        key = request.headers.get("x-auth-key")
        if not username or not key:
            return None
        token = (
            Token.objects.select_related("user")
            .filter(user__username=username, user__is_active=True)
            .first()
        )
        # Hash a dummy when there is no token so a missing user takes the
        # same path as a wrong key.
        expected = self._token_key_md5(token.key if token else "")
        if token is None or not hmac.compare_digest(
            expected.encode(), key.strip().lower().encode()
        ):
            reason = "Unauthorized"
            raise AuthenticationFailed(reason)
        return (token.user, token)

    @override
    def authenticate_header(self, request) -> str:
        """Make DRF answer a failed login with 401, not 403."""
        return "x-auth-key"

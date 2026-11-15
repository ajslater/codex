"""Custom Authentication classes."""

import hashlib
import hmac
from typing import override

from django.contrib.auth.middleware import RemoteUserMiddleware
from rest_framework.authentication import (
    BaseAuthentication,
    BasicAuthentication,
    RemoteUserAuthentication,
    TokenAuthentication,
    get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed

# Models are imported inside functions throughout this module:
# HttpRemoteUserMiddleware here loads with the middleware stack, and models
# must wait for app loading.


def _md5_hex(value: str) -> str:
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()


def get_device_key(secret: str, username: str | None = None):
    """
    Return the active user's device key for a presented secret, or None.

    The one lookup every device-key auth class shares: hash the secret and
    find it. With ``username`` the key must also belong to that user.
    Records the use (at most hourly) on a hit.
    """
    from codex.models.api_key import UserApiKey, device_key_digest

    if not secret:
        return None
    lookup = {"digest": device_key_digest(secret), "user__is_active": True}
    if username is not None:
        lookup["user__username"] = username
    api_key = UserApiKey.objects.select_related("user").filter(**lookup).first()
    if api_key:
        api_key.touch()
    return api_key


def _get_legacy_token(secret: str, username: str):
    """Return the active user's DRF token if it is ``secret``, or None."""
    from rest_framework.authtoken.models import Token

    if not secret:
        return None
    return (
        Token.objects.select_related("user")
        .filter(key=secret, user__username=username, user__is_active=True)
        .first()
    )


class BearerTokenAuthentication(TokenAuthentication):
    """Bearer Token Authentication."""

    keyword = "Bearer"


class DeviceKeyBasicAuthentication(BasicAuthentication):
    """
    OPDS Basic auth that also takes a device key or the bearer token.

    The password may be one of the user's device keys, the user's API
    bearer token, or the account password, checked in that order so key
    logins skip the slow password hash. A key or token must belong to the
    username given. ``request.auth`` is the key or token that matched, or
    None for a password login.
    """

    @override
    def authenticate_credentials(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, userid, password, request=None
    ):
        """
        Try a device key, then the token, then the account password.

        The stubs type ``request.auth`` from Basic as None; here it carries
        the matched credential, which DRF passes through unchanged.
        """
        credential = get_device_key(password, username=userid) or _get_legacy_token(
            password, userid
        )
        if credential:
            return (credential.user, credential)
        return super().authenticate_credentials(userid, password, request)


class DeviceKeyBearerAuthentication(BaseAuthentication):
    """
    OPDS ``Authorization: Bearer <device key>``.

    A Bearer value that is not a device key returns None rather than
    failing, so the legacy :class:`BearerTokenAuthentication` after this
    class still gets to check it as the API token.
    """

    keyword = b"bearer"

    @override
    def authenticate(self, request):
        """Authenticate a Bearer device key, or pass."""
        auth = get_authorization_header(request).split()
        if len(auth) != 2 or auth[0].lower() != self.keyword:  # noqa: PLR2004
            return None
        try:
            secret = auth[1].decode()
        except UnicodeError:
            return None
        api_key = get_device_key(secret)
        if not api_key:
            return None
        return (api_key.user, api_key)


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
    MD5 of the password typed on the device. The password is one of the
    user's device keys or the user's API bearer token, so the key is
    compared with each key's stored ``kosync_digest`` and with the MD5 of
    the user's DRF ``Token``. Only the KOReader views use this class, and
    they use nothing else: no session, no anonymous access.
    """

    @staticmethod
    def _match_device_key(username: str, key: str):
        """Return the user's device key whose MD5 is ``key``, or None."""
        from codex.models.api_key import UserApiKey

        candidates = UserApiKey.objects.select_related("user").filter(
            user__username=username, user__is_active=True
        )
        match = None
        # Compare every candidate rather than look the digest up, so the
        # check stays constant-time against the presented key.
        for candidate in candidates:
            if hmac.compare_digest(candidate.kosync_digest.encode(), key.encode()):
                match = candidate
        if match:
            match.touch()
        return match

    @staticmethod
    def _match_token(username: str, key: str):
        """Return the user's DRF token whose MD5 is ``key``, or None."""
        from rest_framework.authtoken.models import Token

        token = (
            Token.objects.select_related("user")
            .filter(user__username=username, user__is_active=True)
            .first()
        )
        # Hash a dummy when there is no token so a missing user takes the
        # same path as a wrong key.
        expected = _md5_hex(token.key if token else "")
        if token is None or not hmac.compare_digest(expected.encode(), key.encode()):
            return None
        return token

    @override
    def authenticate(self, request):
        """Authenticate the KOReader auth headers against keys and the token."""
        username = request.headers.get("x-auth-user")
        key = request.headers.get("x-auth-key")
        if not username or not key:
            return None
        key = key.strip().lower()
        credential = self._match_device_key(username, key) or self._match_token(
            username, key
        )
        if credential is None:
            reason = "Unauthorized"
            raise AuthenticationFailed(reason)
        return (credential.user, credential)

    @override
    def authenticate_header(self, request) -> str:
        """Make DRF answer a failed login with 401, not 403."""
        return "x-auth-key"

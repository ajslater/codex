"""Custom Authentication classes."""

import hmac
from collections.abc import Collection
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

from codex.choices.api_key import FULL_API_SCOPES, READER_SCOPES, STATS_SCOPES

# Models are imported inside functions throughout this module:
# HttpRemoteUserMiddleware here loads with the middleware stack, and models
# must wait for app loading.


def get_api_key(
    secret: str,
    scopes: Collection[str],
    *,
    username: str | None = None,
    staff_only: bool = False,
):
    """
    Return the API key a presented secret is, or None.

    The one lookup every key auth class shares: hash the secret and find
    it among keys of ``scopes`` whose owner is active. With ``username`` the
    key must also belong to that user; with ``staff_only`` its owner must
    still be staff. Records the use (at most hourly) on a hit.
    """
    from codex.models.api_key import UserApiKey, api_key_digest

    if not secret:
        return None
    lookup = {
        "digest": api_key_digest(secret),
        "scope__in": tuple(scopes),
        "user__is_active": True,
    }
    if username is not None:
        lookup["user__username"] = username
    if staff_only:
        lookup["user__is_staff"] = True
    api_key = UserApiKey.objects.select_related("user").filter(**lookup).first()
    if api_key:
        api_key.touch()
    return api_key


class ApiKeyBearerAuthentication(TokenAuthentication):
    """
    ``Authorization: Bearer <key>`` for keys of :attr:`scopes`.

    The default for ``/api/v4/``, where only universal keys log in: the
    bearer tokens of older versions, migrated. A Bearer value that matches
    no key of the scopes fails the request with 401.
    """

    keyword = "Bearer"
    scopes: Collection[str] = FULL_API_SCOPES

    @override
    def authenticate_credentials(self, key):
        """Look the key up by digest instead of DRF's plaintext token table."""
        api_key = get_api_key(key, self.scopes)
        if not api_key:
            reason = "Invalid token."
            raise AuthenticationFailed(reason)
        return (api_key.user, api_key)


class ReaderKeyBearerAuthentication(ApiKeyBearerAuthentication):
    """OPDS ``Authorization: Bearer``: a device key or a universal key."""

    scopes = READER_SCOPES


class ReaderKeyBasicAuthentication(BasicAuthentication):
    """
    OPDS Basic auth that also takes a device key or a universal key.

    The password may be one of the user's reader keys or the account
    password, in that order so key logins skip the slow password hash. A key
    must belong to the username given. ``request.auth`` is the key that
    matched, or None for a password login.
    """

    @override
    def authenticate_credentials(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, userid, password, request=None
    ):
        """
        Try a reader key, then the account password.

        The stubs type ``request.auth`` from Basic as None; here it carries
        the matched key, which DRF passes through unchanged.
        """
        if api_key := get_api_key(password, READER_SCOPES, username=userid):
            return (api_key.user, api_key)
        return super().authenticate_credentials(userid, password, request)


class StatsKeyAuthentication(BaseAuthentication):
    """
    A Stats API key, as ``?apiKey=<key>`` or ``Authorization: Bearer <key>``.

    Only the admin Stats view uses it, ahead of the default classes. The
    key's owner must still be active staff, and the Stats API Keys admin
    flag must be on: it gates the keys, not the view, so the admin Stats tab
    keeps working by session. A value that is not a stats key returns None,
    so the default classes after this one still get to check a session or a
    universal key.
    """

    _KEYWORD = b"bearer"

    @classmethod
    def _bearer(cls, request) -> str:
        auth = get_authorization_header(request).split()
        if len(auth) != 2 or auth[0].lower() != cls._KEYWORD:  # noqa: PLR2004
            return ""
        try:
            return auth[1].decode()
        except UnicodeError:
            return ""

    @override
    def authenticate(self, request):
        """Authenticate a stats key, or pass. No key logs in while the flag is off."""
        from codex.settings.db import stats_api_enabled

        if not stats_api_enabled():
            return None
        secret = request.query_params.get("apiKey") or self._bearer(request)
        api_key = get_api_key(secret, STATS_SCOPES, staff_only=True)
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
    user's reader keys (a device key or a universal key), so the key is
    compared with each one's stored ``kosync_digest``. Only the KOReader
    views use this class, and they use nothing else: no session, no
    anonymous access.
    """

    # Compared when the user has no reader keys, so a missing user or an
    # unknown one takes the same path as a wrong key.
    _DUMMY_DIGEST = "0" * 32

    @classmethod
    def _match_reader_key(cls, username: str, key: str):
        """Return the user's reader key whose MD5 is ``key``, or None."""
        from codex.models.api_key import UserApiKey

        candidates = tuple(
            UserApiKey.objects.select_related("user").filter(
                user__username=username,
                user__is_active=True,
                scope__in=tuple(READER_SCOPES),
            )
        )
        match = None
        # Compare every candidate rather than look the digest up, so the
        # check stays constant-time against the presented key.
        for candidate in candidates:
            if hmac.compare_digest(candidate.kosync_digest.encode(), key.encode()):
                match = candidate
        if not candidates:
            hmac.compare_digest(cls._DUMMY_DIGEST.encode(), key.encode())
        if match:
            match.touch()
        return match

    @override
    def authenticate(self, request):
        """Authenticate the KOReader auth headers against the reader keys."""
        username = request.headers.get("x-auth-user")
        key = request.headers.get("x-auth-key")
        if not username or not key:
            return None
        key = key.strip().lower()
        api_key = self._match_reader_key(username, key)
        if api_key is None:
            reason = "Unauthorized"
            raise AuthenticationFailed(reason)
        return (api_key.user, api_key)

    @override
    def authenticate_header(self, request) -> str:
        """Make DRF answer a failed login with 401, not 403."""
        return "x-auth-key"

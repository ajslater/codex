"""
Dedicated log of failed-login attempts.

Designed for consumption by IP-banning tools (fail2ban, CrowdSec, sshguard,
etc.) that tail a log and match offending addresses by regex. One record per
failed credential attempt is emitted with ``logger.bind(failed_login=True)``,
which the dedicated loguru sink in :mod:`codex.startup.loguru` filters into a
separate file. The main stdout / codex.log sinks apply the inverse filter
(:func:`not_failed_login_filter`) so the IP-bearing line **only** lands in the
dedicated log — Django's own request logger still records the bare
``"Unauthorized: /api/v3/auth/login/"`` at WARNING so the failure is visible
in the main log, just without the client IP. Concentrating IPs in one place
makes the privacy story easier to reason about (one file to chmod, one file
to forward to a SIEM, one file to retain on a different schedule).

The :class:`RequestContextMiddleware` stashes each request in a
:class:`~contextvars.ContextVar` so the signal handler can recover the client
IP even when the caller did not propagate ``request=`` into Django's
:func:`~django.contrib.auth.authenticate`. ``rest_registration``'s default
login authenticator omits the request, so without this fallback every form-
login failure would log a dash for the IP.
"""

from contextvars import ContextVar
from inspect import iscoroutinefunction
from typing import TYPE_CHECKING, Final

from asgiref.sync import markcoroutinefunction
from loguru import logger

from codex.settings import AUTH_FAILED_LOGIN_LOG_TRUST_FORWARDED_FOR

if TYPE_CHECKING:
    from django.http import HttpRequest

_FAILED_LOGIN_KEY: Final = "failed_login"
_MISSING: Final = "-"
_failed_login_logger = logger.bind(**{_FAILED_LOGIN_KEY: True})
_current_request: ContextVar["HttpRequest | None"] = ContextVar(
    "codex_current_request", default=None
)


def get_client_ip(request: "HttpRequest | None") -> str:
    """Return the client IP, preferring leftmost X-Forwarded-For when trusted."""
    if request is None:
        return _MISSING
    if AUTH_FAILED_LOGIN_LOG_TRUST_FORWARDED_FOR and (
        forwarded := request.META.get("HTTP_X_FORWARDED_FOR", "").strip()
    ):
        return forwarded.split(",", 1)[0].strip() or _MISSING
    return request.META.get("REMOTE_ADDR") or _MISSING


def failed_login_filter(record) -> bool:
    """Loguru sink filter: keep only records tagged via ``logger.bind``."""
    return bool(record["extra"].get(_FAILED_LOGIN_KEY))


def not_failed_login_filter(record) -> bool:
    """
    Loguru sink filter: drop records tagged as failed-login.

    Applied to the main stdout / codex.log sinks so IP-bearing lines stay
    confined to the dedicated log file.
    """
    return not record["extra"].get(_FAILED_LOGIN_KEY)


def on_login_failed(sender, credentials=None, request=None, **_kwargs) -> None:
    """Receiver for ``django.contrib.auth.signals.user_login_failed``."""
    del sender
    if request is None:
        request = _current_request.get()
    ip = get_client_ip(request)
    username = (credentials or {}).get("username") or _MISSING
    _failed_login_logger.warning(f"Failed login from {ip} user={username}")


class RequestContextMiddleware:
    """
    Stash the active request in a contextvar for the signal handler.

    DRF's :class:`~rest_framework.authentication.BasicAuthentication` does
    propagate ``request=`` into :func:`django.contrib.auth.authenticate`, so
    OPDS basic-auth failures already arrive at the signal with a request.
    ``rest_registration``'s default login authenticator does not, so the
    contextvar is the only way to recover the IP for form-login failures.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response) -> None:
        """Initialize response method."""
        self.get_response = get_response
        self._async = iscoroutinefunction(get_response)
        if self._async:
            markcoroutinefunction(self)  # ty: ignore[invalid-argument-type]

    async def _acall(self, request):
        token = _current_request.set(request)
        try:
            return await self.get_response(request)
        finally:
            _current_request.reset(token)

    def __call__(self, request):
        """Set the current-request contextvar around the inner call."""
        if self._async:
            return self._acall(request)
        token = _current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            _current_request.reset(token)

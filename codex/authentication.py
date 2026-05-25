"""Custom Authentication classes."""

from django.contrib.auth.middleware import RemoteUserMiddleware
from rest_framework.authentication import (
    RemoteUserAuthentication,
    TokenAuthentication,
)


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

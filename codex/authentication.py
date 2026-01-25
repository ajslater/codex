"""Custom Authentication classes."""

from django.contrib.auth.middleware import RemoteUserMiddleware
from rest_framework.authentication import TokenAuthentication


class BearerTokenAuthentication(TokenAuthentication):
    """Bearer Token Authentication."""

    keyword = "Bearer"


class HttpRemoteUserMiddleware(RemoteUserMiddleware):
    """
    Http Remote User Backend.

    Regular REMOTE_USER can only be set by on machine wgsi socket magic.
    """

    header = "HTTP_REMOTE_USER"

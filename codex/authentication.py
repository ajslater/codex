"""Custom Authentication classes."""

from rest_framework.authentication import TokenAuthentication


class BearerTokenAuthentication(TokenAuthentication):
    """Bearer Token Authentication."""

    keyword = "Bearer"

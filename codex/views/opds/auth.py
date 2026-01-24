"""OPDS Authentican mixin."""

from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
    TokenAuthentication,
)

from codex.views.auth import AuthMixin


class OPDSAuthMixin(AuthMixin):
    """Add Basic Auth."""

    authentication_classes = (
        TokenAuthentication,
        BasicAuthentication,
        SessionAuthentication,
    )

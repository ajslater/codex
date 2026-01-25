"""OPDS Authentican mixin."""

from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
    TokenAuthentication,
)

from codex.authentication import BearerTokenAuthentication
from codex.views.auth import AuthMixin


class OPDSAuthMixin(AuthMixin):
    """Add Basic Auth."""

    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
        BearerTokenAuthentication,
    )

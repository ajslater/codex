"""OPDS Authentican mixin."""

from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
)

from codex.authentication import BearerTokenAuthentication
from codex.views.auth import AuthMixin


class OPDSAuthMixin(AuthMixin):
    """Add Basic Auth."""

    authentication_classes = (
        BasicAuthentication,
        BearerTokenAuthentication,
        SessionAuthentication,
    )

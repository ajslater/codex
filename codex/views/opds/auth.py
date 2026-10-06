"""OPDS Authentican mixin."""

from functools import cached_property

from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
)

from codex.authentication import BearerTokenAuthentication
from codex.views.auth import AuthMixin
from codex.views.opds.user_agent import get_user_agent_name


class OPDSAuthMixin(AuthMixin):
    """Add Basic Auth."""

    authentication_classes = (
        BasicAuthentication,
        BearerTokenAuthentication,
        SessionAuthentication,
    )

    @cached_property
    def user_agent_name(self) -> str:
        """Memoize the user agent client name."""
        return get_user_agent_name(self.request)

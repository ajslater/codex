"""OPDS Authentican mixin."""

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
    # Class-level default doubles as the unmemoized sentinel so
    # subclasses don't need to redeclare. Lazily resolved on first
    # access via ``user_agent_name`` / ``user_agent_build``.
    _user_agent_parts: tuple[str, int | None] | None = None

    @property
    def _user_agent(self) -> tuple[str, int | None]:
        """Memoize the parsed user agent."""
        if self._user_agent_parts is None:
            self._user_agent_parts = get_user_agent_name(self.request)
        return self._user_agent_parts

    @property
    def user_agent_name(self) -> str:
        """User agent client name."""
        return self._user_agent[0]

    @property
    def user_agent_build(self) -> int | None:
        """User agent build number, for clients whose builds gate features."""
        return self._user_agent[1]

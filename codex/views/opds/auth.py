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

    @property
    def user_agent_name(self) -> str:
        """Memoize user agent name."""
        if self._user_agent_name is None:  # pyright: ignore[reportUnnecessaryComparison]
            self._user_agent_name = get_user_agent_name(self.request)  # pyright: ignore[reportAttributeAccessIssue,reportUninitializedInstanceVariable], # ty: ignore[unresolved-attribute]
        return self._user_agent_name

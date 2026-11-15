"""OPDS Authentican mixin."""

from functools import cached_property

from rest_framework.authentication import SessionAuthentication

from codex.authentication import (
    ReaderKeyBasicAuthentication,
    ReaderKeyBearerAuthentication,
)
from codex.views.auth import AuthMixin
from codex.views.opds.user_agent import get_user_agent_name


class OPDSAuthMixin(AuthMixin):
    """
    Add Basic and Bearer auth with reader keys, then the session.

    Reader keys (device keys and the universal keys migrated from old
    bearer tokens) log in here and on KOReader sync. Basic also takes the
    account password. ``request.auth`` is the key that matched.
    """

    authentication_classes = (
        ReaderKeyBasicAuthentication,
        ReaderKeyBearerAuthentication,
        SessionAuthentication,
    )

    @cached_property
    def user_agent_name(self) -> str:
        """Memoize the user agent client name."""
        return get_user_agent_name(self.request)

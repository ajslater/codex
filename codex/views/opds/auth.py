"""OPDS Authentican mixin."""

from functools import cached_property

from rest_framework.authentication import SessionAuthentication

from codex.authentication import (
    BearerTokenAuthentication,
    DeviceKeyBasicAuthentication,
    DeviceKeyBearerAuthentication,
)
from codex.views.auth import AuthMixin
from codex.views.opds.user_agent import get_user_agent_name


class OPDSAuthMixin(AuthMixin):
    """
    Add Basic and Bearer auth, with device keys.

    Device keys authenticate here and on KOReader sync only; the default
    DRF classes for ``/api/v4/`` never see them. The device Bearer class
    passes on a value that is not a device key, so the legacy token class
    after it still checks the API token.
    """

    authentication_classes = (
        DeviceKeyBasicAuthentication,
        DeviceKeyBearerAuthentication,
        BearerTokenAuthentication,
        SessionAuthentication,
    )

    @cached_property
    def user_agent_name(self) -> str:
        """Memoize the user agent client name."""
        return get_user_agent_name(self.request)

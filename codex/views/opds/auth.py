"""OPDS Authentican mixin."""

from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.template import CodexXMLTemplateView


class OPDSAuthMixin:
    """Add Basic Auth."""

    authentication_classes = (BasicAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticatedOrEnabledNonUsers,)


class OPDSTemplateView(OPDSAuthMixin, CodexXMLTemplateView):
    """XML Template view with OPDSAuth."""

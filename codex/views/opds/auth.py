"""OPDS Authentican mixin."""

from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.template import CodexXMLTemplateMixin


class OPDSAuthMixin:
    """Add Basic Auth."""

    authentication_classes = (BasicAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticatedOrEnabledNonUsers,)


class OPDSTemplateMixin(OPDSAuthMixin, CodexXMLTemplateMixin):
    """XML Template view with OPDSAuth."""

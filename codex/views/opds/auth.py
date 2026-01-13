"""OPDS Authentican mixin."""

from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from codex.views.auth import AuthMixin
from codex.views.template import CodexXMLTemplateMixin


class OPDSAuthMixin(AuthMixin):
    """Add Basic Auth."""

    authentication_classes = (BasicAuthentication, SessionAuthentication)


class OPDSTemplateMixin(OPDSAuthMixin, CodexXMLTemplateMixin):
    """XML Template view with OPDSAuth."""

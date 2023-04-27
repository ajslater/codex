"""OPDS Authentication 1.0."""
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse_lazy
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from codex.serializers.opds.authentication import OPDSAuthentication1Serializer


class OPDSAuthentication1View(GenericAPIView):
    """Authentication document."""

    serializer_class = OPDSAuthentication1Serializer

    DOC = {
        "id": reverse_lazy("opds:authentication:v1"),
        "title": "Codex",
        "description": "Codex OPDS Syndication",
        "links": [
            {
                "rel": "logo",
                "href": staticfiles_storage.url("img/logo.svg"),
                "type": "image/svg+xml",
                "width": 512,
                "height": 512,
            },
            {
                "rel": "help",
                "href": "https://github.com/ajslater/codex",
                "type": "text/html",
            },
            {
                "rel": "register",
                "href": reverse_lazy("app:start"),
                "type": "text/html",
            },
        ],
        "authentication": [
            {
                "type": "http://opds-spec.org/auth/basic",
                "labels": {"login": "Username", "password": "Password"},
            },
            {
                # XXX Out of spec type
                "type": "cookie",
                "links": [
                    {
                        "rel": "authenticate",
                        "href": reverse_lazy("app:start"),
                        "type": "text/html",
                    }
                ],
            },
        ],
    }

    def get(self, *args, **kwargs):
        """Fill in the authentication dict."""
        serializer = self.get_serializer(self.DOC)
        return Response(serializer.data)

"""OPDS Authentication 1.0."""
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse_lazy
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from codex.serializers.opds_v1 import AuthenticationSerializer


class AuthenticationView(GenericAPIView):
    """Authentication document."""

    serializer_class = AuthenticationSerializer

    DOC = {
        "id": reverse_lazy("opds:v1:authentication"),
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
                "type": "text/hml",
            },
            {
                "rel": "register",
                "href": reverse_lazy("app:start"),
                "type": "text/hml",
            },
        ],
        "authentication": [
            {
                "type": "http://opds-spec.org/auth/basic",
                "labels": {"login": "Username", "password": "Password"},
            }
        ],
    }

    def get(self, request, *args, **kwargs):
        """Fill in the authentication dict."""
        serializer = self.get_serializer(self.DOC)
        return Response(serializer.data)

"""OPDS Authentication 1.0."""
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse_lazy
from rest_framework.response import Response
from rest_framework.views import APIView


class AuthenticationView(APIView):
    """Authentication document."""

    def get(self, request, *args, **kwargs):
        """Fill in the authentication dict."""
        doc = {
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
                    "href": reverse_lazy("app"),
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
        return Response(doc)

"""OPDS Authentication 1.0."""

from re import DEBUG
from types import MappingProxyType

from django.contrib.staticfiles.storage import staticfiles_storage
from django.http.response import JsonResponse
from django.urls import reverse_lazy
from rest_framework import status
from rest_framework.generics import GenericAPIView

from codex.serializers.opds.authentication import OPDSAuthentication1Serializer
from codex.views.opds.const import MimeType, UserAgentNames
from codex.views.opds.util import get_user_agent_name

_LOGO_SIZE = 180
_DOC = MappingProxyType(
    {
        "id": reverse_lazy("opds:auth:v1"),
        "title": "Codex",
        "description": "Enter your username and password to authenticate",
        "links": [
            {
                "rel": "logo",
                "href": staticfiles_storage.url("img/logo-maskable-180.webp"),
                "type": MimeType.WEBP,
                "width": _LOGO_SIZE,
                "height": _LOGO_SIZE,
            },
            {
                "rel": "help",
                "href": "https://codex-comic-reader.readthedocs.io/",
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
        ],
    }
)


class OPDSAuthentication1View(GenericAPIView):
    """Authentication document."""

    serializer_class = OPDSAuthentication1Serializer

    @staticmethod
    def _absolute_doc(request):
        """Absolutize the logo link url."""
        doc = dict(_DOC)
        logo_link: dict[str, str | int] = doc["links"][0]  # pyright: ignore[reportAssignmentType]
        href = logo_link["href"]
        href = request.build_absolute_uri(href)
        logo_link["href"] = href
        return doc

    @classmethod
    def static_get(cls, request, status_code=status.HTTP_200_OK):
        """Serialize the authentication dict."""
        user_agent_name = get_user_agent_name(request)
        if DEBUG or user_agent_name in UserAgentNames.REQUIRE_ABSOLUTE_URL:
            doc = cls._absolute_doc(request)
        else:
            doc = _DOC
        serializer = cls.serializer_class(doc)  # pyright: ignore[reportOptionalCall]
        return JsonResponse(serializer.data, status=status_code)

    def get(self, *args, **kwargs):
        """Get authentication response."""
        return self.static_get(self.request)

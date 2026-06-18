"""OPDS Authentication 1.0."""

from types import MappingProxyType

from django.contrib.staticfiles.storage import staticfiles_storage
from django.http.response import JsonResponse
from django.urls import reverse_lazy
from rest_framework import status
from rest_framework.generics import GenericAPIView

from codex.serializers.opds.authentication import OPDSAuthentication1Serializer
from codex.views.opds.const import MimeType

_LOGO_SIZE = 180
_BASIC_AUTH_REALM = "Codex OPDS"
_WWW_AUTHENTICATE_BASIC = f'Basic realm="{_BASIC_AUTH_REALM}"'
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
    def _absolute_doc(request) -> dict:
        """
        Return the auth document with absolute URLs.

        OPDS Authentication's ``id`` is the document's canonical location — a
        ``format: uri`` (absolute) value — and strict clients (e.g. Stump)
        reject a relative ``id`` (or relative link hrefs). Build a fresh copy so
        the module-level ``_DOC`` singleton is never mutated; ``build_absolute_uri``
        leaves already-absolute hrefs (e.g. the help link) untouched.
        """
        doc = dict(_DOC)
        doc["id"] = request.build_absolute_uri(str(_DOC["id"]))
        links: list[dict[str, str | int]] = _DOC["links"]  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
        doc["links"] = [
            {**link, "href": request.build_absolute_uri(str(link["href"]))}
            for link in links
        ]
        return doc

    @classmethod
    def static_get(cls, request, status_code=status.HTTP_200_OK) -> JsonResponse:
        """Serialize the authentication dict with absolute URLs."""
        doc = cls._absolute_doc(request)
        serializer = cls.serializer_class(doc)  # pyright: ignore[reportOptionalCall]
        response = JsonResponse(
            serializer.data,
            status=status_code,
            content_type=MimeType.AUTHENTICATION,
        )
        if status_code == status.HTTP_401_UNAUTHORIZED:
            # RFC 7235: 401 must include WWW-Authenticate; some OPDS clients require it to trigger an auth prompt.
            response["WWW-Authenticate"] = _WWW_AUTHENTICATE_BASIC
        return response

    def get(self, *args, **kwargs) -> JsonResponse:
        """Get authentication response."""
        return self.static_get(self.request)

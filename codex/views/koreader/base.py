"""
Shared base for the KOReader kosync views.

KOReader's kosync plugin speaks the koreader-sync-server protocol: JSON with
``Accept: application/vnd.koreader.v1+json``, credentials in ``x-auth-user``
and ``x-auth-key``, and error bodies carrying ``code`` and ``message``. These
views answer that protocol and nothing else: they 404 while the KOReader Sync
admin flag is off and never fall back to session auth or Non Users.
"""

from http import HTTPStatus
from typing import Final, override

from django.http import Http404
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    ParseError,
)
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.authentication import KOSyncAuthentication
from codex.settings.db import koreader_sync_enabled

# koreader-sync-server's error codes.
ERROR_UNAUTHORIZED: Final = 2001
ERROR_INVALID_FIELDS: Final = 2003
ERROR_DOCUMENT_FIELD_MISSING: Final = 2004
ERROR_REGISTRATION_DISABLED: Final = 2005
_ERROR_NOT_FOUND: Final = 2000


def kosync_error(status: HTTPStatus, code: int, message: str) -> Response:
    """Return a kosync error body."""
    return Response({"code": code, "message": message}, status=status)


class KOSyncJSONParser(JSONParser):
    """
    Parse every request body as JSON, whatever its Content-Type.

    KOReader sends JSON; some builds label it with the vendor media type.
    """

    media_type = "*/*"


class KOSyncContentNegotiation(BaseContentNegotiation):
    """Always answer JSON: KOReader's vendor Accept type is JSON."""

    @override
    def select_parser(self, request, parsers):
        """Use the only parser."""
        return next(iter(parsers))

    @override
    def select_renderer(self, request, renderers, format_suffix=None):
        """Use the only renderer."""
        renderer = next(iter(renderers))
        return renderer, renderer.media_type


class KOSyncAPIView(APIView):
    """Base for kosync endpoints."""

    authentication_classes = (KOSyncAuthentication,)
    permission_classes = (IsAuthenticated,)
    parser_classes = (KOSyncJSONParser,)
    renderer_classes = (JSONRenderer,)

    @override
    def get_content_negotiator(self) -> KOSyncContentNegotiation:
        """Ignore Accept: KOReader's vendor media type is JSON."""
        return KOSyncContentNegotiation()

    @override
    def initial(self, request, *args, **kwargs) -> None:
        """404 everything while the flag is off, before authenticating."""
        if not koreader_sync_enabled():
            raise Http404
        super().initial(request, *args, **kwargs)

    @override
    def handle_exception(self, exc) -> Response:
        """Answer in kosync's error shape."""
        if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
            return kosync_error(
                HTTPStatus.UNAUTHORIZED, ERROR_UNAUTHORIZED, "Unauthorized"
            )
        if isinstance(exc, (Http404, NotFound)):
            return kosync_error(HTTPStatus.NOT_FOUND, _ERROR_NOT_FOUND, "Not found")
        if isinstance(exc, ParseError):
            return kosync_error(
                HTTPStatus.BAD_REQUEST, ERROR_INVALID_FIELDS, "Invalid request"
            )
        return super().handle_exception(exc)

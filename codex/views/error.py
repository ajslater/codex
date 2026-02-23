"""Custom Http Error Views."""

from django.http.response import HttpResponseRedirect, JsonResponse
from rest_framework.response import Response
from rest_framework.views import exception_handler

from codex.views.opds.error import OPDS_PATH_PREFIX, codex_opds_exception_handler


def codex_exception_handler(
    exc, context
) -> JsonResponse | None | HttpResponseRedirect | Response:
    """Assume OPDS clients want redirects instead of errors."""
    response = None
    request = context.get("request")
    if OPDS_PATH_PREFIX in request.path:
        response = codex_opds_exception_handler(exc, context)
    if not response:
        response = exception_handler(exc, context)

    return response

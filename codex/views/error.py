"""Custom Http Error Views."""

from django.shortcuts import redirect
from django.urls import reverse
from rest_framework import status
from rest_framework.views import exception_handler

from codex.views.exceptions import SeeOtherRedirectError

_OPDS_PATH_PREFIX = "opds/v"
_RESET_TOP_GROUP_QUERY = "?topGroup=p"


def codex_exception_handler(exc, context):
    """Assume OPDS clients want redirects instead of errors."""
    response = None
    request = context.get("request")
    if _OPDS_PATH_PREFIX in request.path:
        name = (
            "opds:v2:feed"
            if _OPDS_PATH_PREFIX + "2" in request.path
            else "opds:v1:feed"
        )
        if isinstance(exc, SeeOtherRedirectError):
            response = exc.get_response(name)
        elif hasattr(exc, "status_code") and exc.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ):
            url = reverse(name)
            url += _RESET_TOP_GROUP_QUERY
            response = redirect(url, permanent=False)

    if not response:
        response = exception_handler(exc, context)

    return response

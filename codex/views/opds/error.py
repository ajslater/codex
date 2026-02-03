"""Custom Http Error Views."""

from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from rest_framework import status
from rest_framework.views import exception_handler

from codex.views.exceptions import SeeOtherRedirectError
from codex.views.opds.authentication.v1 import OPDSAuthentication1View

OPDS_PATH_PREFIX = "opds/v"
_OPDS_V2_PATH_PREFIX = OPDS_PATH_PREFIX + "2"
_RESET_TOP_GROUP_QUERY = "?topGroup=p"
_OPDS_REDIRECT_TO_AUTH_CODES = frozenset({status.HTTP_401_UNAUTHORIZED})
_OPDS_REDIRECT_TO_TOP_CODES = frozenset(
    {
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_405_METHOD_NOT_ALLOWED,
        status.HTTP_410_GONE,
        status.HTTP_414_REQUEST_URI_TOO_LONG,
    }
)


def _get_url_name(request: HttpRequest, name_suffix: str):
    version = "2" if _OPDS_V2_PATH_PREFIX in request.path else "1"
    return f"opds:v{version}:{name_suffix}"


def _get_redirect_to_start_response(request: HttpRequest):
    """Get a redirect to the start."""
    name = _get_url_name(request, "start")
    url = reverse(name)
    return redirect(url, permanent=False)


def codex_opds_exception_handler(exc, context):
    """
    Assume OPDS clients want redirects instead of errors.

    Except for Authentication which requires inline auth JSON.
    """
    response = None
    request = context.get("request")
    if isinstance(exc, SeeOtherRedirectError):
        name = _get_url_name(request, "feed")
        response = exc.get_response(name)
    elif status_code := getattr(exc, "status_code", None):
        if status_code == status.HTTP_403_FORBIDDEN:
            # Codex presents 403 sometimes when it should be presenting 401
            status_code = status.HTTP_401_UNAUTHORIZED
        if status_code in _OPDS_REDIRECT_TO_AUTH_CODES:
            response = OPDSAuthentication1View.static_get(request, status_code)
        elif (
            not request.path.endswith("progression")
            and status_code in _OPDS_REDIRECT_TO_TOP_CODES
        ):
            response = _get_redirect_to_start_response(request)

    if not response:
        response = exception_handler(exc, context)

    return response

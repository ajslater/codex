"""Custom Http Error Views."""

from django.shortcuts import redirect
from django.urls import reverse
from rest_framework import status

from codex.views.exceptions import SeeOtherRedirectError
from codex.views.opds.authentication_v1 import OPDSAuthentication1View

OPDS_PATH_PREFIX = "opds/v"
_OPDS_V2_PATH_PREFIX = OPDS_PATH_PREFIX + "2"
_RESET_TOP_GROUP_QUERY = "?topGroup=p"
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
_OPDS_REDIRECT_TO_AUTH_CODES = frozenset({status.HTTP_401_UNAUTHORIZED})


def codex_opds_exception_handler(exc, context):
    """
    Assume OPDS clients want redirects instead of errors.

    Except for Authentication which requires inline auth JSON.
    """
    response = None
    request = context.get("request")
    version = "2" if _OPDS_V2_PATH_PREFIX in request.path else "1"
    name = f"opds:v{version}:feed"
    if isinstance(exc, SeeOtherRedirectError):
        response = exc.get_response(name)
    elif status_code := getattr(exc, "status_code", None):
        if status_code == status.HTTP_403_FORBIDDEN:
            status_code = status.HTTP_401_UNAUTHORIZED
        if status_code in _OPDS_REDIRECT_TO_TOP_CODES:
            url = reverse(name)
            url += _RESET_TOP_GROUP_QUERY
            response = redirect(url, permanent=False)
        elif status_code in _OPDS_REDIRECT_TO_AUTH_CODES:
            response = OPDSAuthentication1View.static_get(request, status_code)

    return response

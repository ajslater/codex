"""Custom Http Error Views."""
from django.shortcuts import redirect
from django.urls import reverse
from rest_framework import status
from rest_framework.views import exception_handler

from codex.exceptions import SeeOtherRedirectError


def codex_exception_handler(exc, context):
    """Assume OPDS clients want redirects instead of errors."""
    response = None
    request = context.get("request")
    opds_start = reverse("opds:start")
    if request.path.startswith(opds_start):
        if isinstance(exc, SeeOtherRedirectError):
            response = exc.get_response("opds:v1:browser")
        elif hasattr(exc, "status_code") and exc.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ):
            response = redirect(opds_start, permanent=False)

    if not response:
        response = exception_handler(exc, context)

    return response

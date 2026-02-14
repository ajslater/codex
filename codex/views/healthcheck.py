"""Docker Healthcheck."""

from django.http import HttpResponse


def health_check_view(request) -> HttpResponse:  # noqa: ARG001
    """Return OK."""
    return HttpResponse("Ok")

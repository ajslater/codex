"""OPDS start view."""
from django.http.response import HttpResponseRedirect
from django.urls import reverse

from codex.serializers.choices import DEFAULTS


def opds_start_view(request):
    """Redirect to start view, forwarding query strings and auth."""
    kwargs = DEFAULTS["route"]
    url = reverse("opds:v1:browser", kwargs=kwargs)

    # Forward the query string.
    path = request.get_full_path()
    if path:
        parts = path.split("?")
        if len(parts) >= 2:
            parts[0] = url
            url = "?".join(parts)

    response = HttpResponseRedirect(url)

    # Forward authorization.
    auth_header = request.META.get("HTTP_AUTHORIZATION")
    if auth_header:
        response["HTTP_AUTHORIZATION"] = auth_header

    return response

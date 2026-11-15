"""
The API URLs for the API Access dialog.

``GET /api/v4/api-urls`` returns the path of each API this visitor may use,
and leaves out every API that is turned off or not theirs to use: OPDS for
anyone who may browse, KOReader sync for a logged-in user, the Stats API for
staff. The paths are relative to the origin and carry any
``url_path_prefix``.
"""

from django.urls import reverse
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.serializers.api_urls import ApiUrlsSerializer
from codex.settings.db import koreader_sync_enabled, opds_enabled, stats_api_enabled
from codex.views.auth import AuthGenericAPIView

# KOReader appends the kosync paths to the server URL, so the URL is the
# route prefix, without a trailing slash.
_KOREADER_PROBE = "healthcheck"


def _koreader_url() -> str:
    return reverse("koreader:healthcheck").removesuffix(_KOREADER_PROBE).rstrip("/")


class ApiUrlsView(AuthGenericAPIView):
    """The URLs of the APIs this visitor may use."""

    serializer_class: type[BaseSerializer] | None = ApiUrlsSerializer

    def get(self, *_args, **_kwargs) -> Response:
        """Resolve the URLs of the APIs that are on and permitted."""
        user = self.request.user
        urls: dict[str, str] = {}
        if opds_enabled():
            # The start routes carry no path params: the catalog root.
            urls["opds_v1"] = reverse("opds:v1:start")
            urls["opds_v2"] = reverse("opds:v2:start")
        if user.is_authenticated and koreader_sync_enabled():
            urls["koreader"] = _koreader_url()
        if getattr(user, "is_staff", False) and stats_api_enabled():
            urls["stats"] = reverse("api:v4:admin:stats")
        serializer = self.get_serializer(urls)
        return Response(serializer.data)

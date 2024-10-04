"""OPDS URLs."""

from django.urls import reverse
from rest_framework.response import Response

from codex.choices import DEFAULT_BROWSER_ROUTE
from codex.serializers.opds.urls import OPDSURLsSerializer
from codex.views.auth import AuthGenericAPIView
from codex.views.util import pop_name

_OPDS_VERSIONS = (1, 2)


class OPDSURLsView(AuthGenericAPIView):
    """OPDS URLs."""

    serializer_class = OPDSURLsSerializer

    def get(self, *args, **kwargs):
        """Resolve the urls."""
        obj = {}
        route = DEFAULT_BROWSER_ROUTE
        route = pop_name(route)
        for version in _OPDS_VERSIONS:
            key = f"v{version}"
            name = f"opds:v{version}:feed"
            value = reverse(name, kwargs=route)
            obj[key] = value
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

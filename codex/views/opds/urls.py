"""OPDS URLs."""

from django.urls import reverse
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from codex.serializers.choices import DEFAULTS
from codex.serializers.opds.urls import OPDSURLsSerializer

OPDS_VERSIONS = (1, 2)


class OPDSURLsView(GenericAPIView):
    """OPDS URLs."""

    serializer_class = OPDSURLsSerializer

    def get(self, *args, **kwargs):
        """Resolve the urls."""
        obj = {}
        route = DEFAULTS["breadcrumbs"][0]
        for version in OPDS_VERSIONS:
            key = f"v{version}"
            name = f"opds:v{version}:feed"
            value = reverse(name, kwargs=route)
            obj[key] = value
        serializer = self.get_serializer(obj)
        return Response(serializer.data)
